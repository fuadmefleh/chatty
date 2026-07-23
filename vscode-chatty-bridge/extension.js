// @ts-check

const vscode = require('vscode');
const http = require('http');
const https = require('https');
const { execSync } = require('child_process');

/** @type {vscode.StatusBarItem} */
let statusBarItem;

/** @type {NodeJS.Timeout | undefined} */
let pollTimer;

/** @type {string | undefined} */
let currentRequestId;

/** @type {vscode.OutputChannel} */
let outputChannel;

/** @type {vscode.Disposable[]} */
let fileWatchers = [];

/** @type {Set<string>} */
let changedFiles = new Set();

/** @type {NodeJS.Timeout | undefined} */
let idleTimer;

/** @type {number} */
let lastFileChangeTime = 0;

/** @type {boolean} */
let agentStartedEditing = false;

const IDLE_TIMEOUT_MS = 45000;  // 45s of no file changes = agent is done
const WORKSPACE_ROOT = '/home/edgeworks-server/chatty';

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    outputChannel = vscode.window.createOutputChannel('Atlas Bridge');
    log('Atlas Bridge extension activated');

    // Status bar
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'chatty-bridge.showQueue';
    statusBarItem.tooltip = 'Atlas Bridge - Click to show queue';
    updateStatusBar('idle');
    statusBarItem.show();

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('chatty-bridge.checkNow', () => checkForRequests()),
        vscode.commands.registerCommand('chatty-bridge.completeRequest', () => completeCurrentRequest()),
        vscode.commands.registerCommand('chatty-bridge.failRequest', () => failCurrentRequest()),
        vscode.commands.registerCommand('chatty-bridge.togglePolling', () => togglePolling()),
        vscode.commands.registerCommand('chatty-bridge.showQueue', () => showQueue()),
        statusBarItem,
        outputChannel
    );

    // Start polling if enabled
    const config = vscode.workspace.getConfiguration('chattyBridge');
    if (config.get('enabled', true)) {
        startPolling();
    }
}

function deactivate() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = undefined;
    }
    disposeFileWatchers();
}

// ============================================================================
// Polling
// ============================================================================

function startPolling() {
    const config = vscode.workspace.getConfiguration('chattyBridge');
    const intervalSec = config.get('pollInterval', 10);

    if (pollTimer) {
        clearInterval(pollTimer);
    }

    pollTimer = setInterval(() => checkForRequests(), intervalSec * 1000);
    updateStatusBar('polling');
    log(`Polling started (every ${intervalSec}s)`);
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = undefined;
    }
    updateStatusBar('stopped');
    log('Polling stopped');
}

function togglePolling() {
    if (pollTimer) {
        stopPolling();
        vscode.window.showInformationMessage('Atlas Bridge: Polling stopped');
    } else {
        startPolling();
        vscode.window.showInformationMessage('Atlas Bridge: Polling started');
    }
}

// ============================================================================
// Request checking
// ============================================================================

async function checkForRequests() {
    // Don't check if we're already processing a request
    if (currentRequestId) {
        return;
    }

    try {
        const data = await apiGet('/api/vscode/requests?status=pending');

        if (!data.success || !data.requests || data.requests.length === 0) {
            return;
        }

        const request = data.requests[0]; // Process oldest first
        log(`New request found: ${request.id.substring(0, 8)}... - ${request.message.substring(0, 80)}`);

        const config = vscode.workspace.getConfiguration('chattyBridge');
        const autoSend = config.get('autoSend', true);

        if (autoSend) {
            await processRequest(request);
        } else {
            const action = await vscode.window.showInformationMessage(
                `Atlas code request: ${request.message.substring(0, 100)}${request.message.length > 100 ? '...' : ''}`,
                'Send to Copilot',
                'Dismiss'
            );

            if (action === 'Send to Copilot') {
                await processRequest(request);
            } else {
                log('Request dismissed by user');
            }
        }
    } catch (err) {
        // Server might not be running - that's OK, just log quietly
        log(`Poll check failed: ${err.message}`);
    }
}

async function processRequest(request) {
    currentRequestId = request.id;
    updateStatusBar('processing');

    // Mark as in_progress on the server
    try {
        await apiPut(`/api/vscode/requests/${request.id}`, {
            status: 'in_progress'
        });
    } catch (err) {
        log(`Failed to update status: ${err.message}`);
    }

    // Start file watchers to track what the agent changes
    startFileWatching(request.id);

    // Send initial progress update
    await sendUpdate(request.id, 'started', `Processing request: ${request.message.substring(0, 100)}`);

    // Build the prompt for Copilot
    const prompt = buildCopilotPrompt(request);

    log(`Sending to Copilot: ${prompt.substring(0, 200)}...`);

    try {
        // Send to Copilot chat in agent mode
        await vscode.commands.executeCommand('workbench.action.chat.open', {
            query: prompt,
            isPartialQuery: false
        });

        await sendUpdate(request.id, 'agent_started', 'Copilot agent is now working on the request...');

        // Start the idle detection timer - agent is "done" when files stop changing
        startIdleDetection(request.id);

    } catch (err) {
        log(`Error sending to Copilot: ${err.message}`);
        await sendUpdate(request.id, 'error', `Extension error: ${err.message}`);
        await updateRequestStatus(request.id, 'failed', `Extension error: ${err.message}`);
        disposeFileWatchers();
        currentRequestId = undefined;
        updateStatusBar('polling');
    }
}

// ============================================================================
// File watching & progress streaming
// ============================================================================

function startFileWatching(requestId) {
    disposeFileWatchers();
    changedFiles.clear();
    agentStartedEditing = false;
    lastFileChangeTime = Date.now();

    // Watch for file saves in the workspace
    const saveWatcher = vscode.workspace.onDidSaveTextDocument((doc) => {
        const relativePath = vscode.workspace.asRelativePath(doc.uri);
        // Ignore the queue file itself and other non-code files
        if (relativePath.includes('vscode_requests.json') || relativePath.includes('node_modules')) {
            return;
        }

        const isNew = !changedFiles.has(relativePath);
        changedFiles.add(relativePath);
        lastFileChangeTime = Date.now();
        agentStartedEditing = true;

        if (isNew) {
            log(`File saved: ${relativePath}`);
            sendUpdate(requestId, 'file_saved', `Saved: ${relativePath}`);
        }
    });

    // Watch for new file creation
    const createWatcher = vscode.workspace.onDidCreateFiles((e) => {
        for (const uri of e.files) {
            const relativePath = vscode.workspace.asRelativePath(uri);
            if (relativePath.includes('node_modules')) continue;

            changedFiles.add(relativePath);
            lastFileChangeTime = Date.now();
            agentStartedEditing = true;
            log(`File created: ${relativePath}`);
            sendUpdate(requestId, 'file_created', `Created: ${relativePath}`);
        }
    });

    // Watch for file deletions
    const deleteWatcher = vscode.workspace.onDidDeleteFiles((e) => {
        for (const uri of e.files) {
            const relativePath = vscode.workspace.asRelativePath(uri);
            lastFileChangeTime = Date.now();
            agentStartedEditing = true;
            log(`File deleted: ${relativePath}`);
            sendUpdate(requestId, 'file_deleted', `Deleted: ${relativePath}`);
        }
    });

    fileWatchers.push(saveWatcher, createWatcher, deleteWatcher);
    log('File watchers started');
}

function disposeFileWatchers() {
    for (const w of fileWatchers) {
        w.dispose();
    }
    fileWatchers = [];
    if (idleTimer) {
        clearInterval(idleTimer);
        idleTimer = undefined;
    }
}

function startIdleDetection(requestId) {
    if (idleTimer) {
        clearInterval(idleTimer);
    }

    // Check every 5 seconds if agent has gone idle
    idleTimer = setInterval(async () => {
        const elapsed = Date.now() - lastFileChangeTime;

        // Agent must have started editing before we consider it "done"
        if (agentStartedEditing && elapsed >= IDLE_TIMEOUT_MS) {
            log(`Agent idle for ${Math.round(elapsed / 1000)}s - auto-completing`);
            clearInterval(idleTimer);
            idleTimer = undefined;
            await autoCompleteRequest(requestId);
        }
    }, 5000);
}

async function autoCompleteRequest(requestId) {
    // Generate a summary of changes
    const summary = await generateChangeSummary();

    await sendUpdate(requestId, 'completed', summary);
    await updateRequestStatus(requestId, 'completed', summary);

    // Determine which services need restarting based on changed files
    const restartServices = getServicesToRestart();
    if (restartServices.length > 0) {
        await sendUpdate(requestId, 'restarting', `Restarting ${restartServices.join(', ')} to pick up changes...`);
        await triggerRestart(restartServices);
    }

    disposeFileWatchers();
    currentRequestId = undefined;
    updateStatusBar('polling');
    log(`Request ${requestId.substring(0, 8)}... auto-completed`);
    vscode.window.showInformationMessage(`Atlas request auto-completed. ${changedFiles.size} file(s) changed.`);
}

async function generateChangeSummary() {
    const parts = [];

    if (changedFiles.size > 0) {
        parts.push(`**Files changed (${changedFiles.size}):**`);
        for (const f of changedFiles) {
            parts.push(`- ${f}`);
        }
    }

    // Try to get git diff stat
    try {
        const diff = execSync('git diff --stat HEAD', {
            cwd: WORKSPACE_ROOT,
            encoding: 'utf8',
            timeout: 5000
        }).trim();
        if (diff) {
            parts.push('', '**Git diff:**', diff);
        }
    } catch {
        // git not available or not a repo - that's fine
    }

    return parts.length > 0 ? parts.join('\n') : 'Request completed (no file changes detected).';
}

/**
 * Send a progress update to the API
 * @param {string} requestId
 * @param {string} type
 * @param {string} content
 */
async function sendUpdate(requestId, type, content) {
    try {
        await apiPost(`/api/vscode/requests/${requestId}/updates`, { type, content });
        log(`Update sent [${type}]: ${content.substring(0, 100)}`);
    } catch (err) {
        log(`Failed to send update: ${err.message}`);
    }
}

/**
 * Determine which pm2 services need restarting based on which files changed.
 * @returns {string[]}
 */
function getServicesToRestart() {
    const services = new Set();

    for (const file of changedFiles) {
        // Bot code: src/, skills/, anything .py in root
        if (file.startsWith('src/') || file.startsWith('skills/') || 
            (file.endsWith('.py') && !file.includes('/'))) {
            services.add('chatty-bot');
        }
        // Mini app server
        if (file === 'mini_app_server.py' || file.startsWith('skills/vscode_bridge/')) {
            services.add('chatty-mini-apps');
        }
    }

    // Default to restarting bot if any python file changed
    if (services.size === 0) {
        for (const file of changedFiles) {
            if (file.endsWith('.py')) {
                services.add('chatty-bot');
                break;
            }
        }
    }

    return Array.from(services);
}

/**
 * Trigger a delayed pm2 restart via the API.
 * @param {string[]} services
 */
async function triggerRestart(services) {
    try {
        await apiPost('/api/vscode/restart', { services, delay: 5 });
        log(`Restart triggered for: ${services.join(', ')}`);
    } catch (err) {
        log(`Failed to trigger restart: ${err.message}`);
    }
}

function buildCopilotPrompt(request) {
    return [
        `The following is a code change request from the Atlas bot user (sent via Telegram).`,
        `Please implement the requested changes in the workspace.`,
        ``,
        `## Request`,
        `${request.message}`,
        ``,
        `## Context`,
        `- Request ID: ${request.id}`,
        `- Workspace: /home/edgeworks-server/chatty`,
        `- This is the Atlas bot codebase (Telegram bot with ReACT agent, skills system, memory system)`,
        ``,
        `After making changes, provide a brief summary of what was changed.`
    ].join('\n');
}

// ============================================================================
// Request status management
// ============================================================================

async function completeCurrentRequest() {
    if (!currentRequestId) {
        vscode.window.showWarningMessage('No active request to complete');
        return;
    }

    const result = await vscode.window.showInputBox({
        prompt: 'Brief summary of changes made (optional)',
        placeHolder: 'e.g., Added monthly breakdown to budget analysis'
    });

    await updateRequestStatus(currentRequestId, 'completed', result || 'Completed via VS Code');
    log(`Request ${currentRequestId.substring(0, 8)}... marked as completed`);

    // Restart services if files were changed
    const restartServices = getServicesToRestart();
    if (restartServices.length > 0) {
        await sendUpdate(currentRequestId, 'restarting', `Restarting ${restartServices.join(', ')} to pick up changes...`);
        await triggerRestart(restartServices);
    }

    vscode.window.showInformationMessage('Request marked as completed');
    disposeFileWatchers();
    currentRequestId = undefined;
    updateStatusBar('polling');
}

async function failCurrentRequest() {
    if (!currentRequestId) {
        vscode.window.showWarningMessage('No active request to fail');
        return;
    }

    const reason = await vscode.window.showInputBox({
        prompt: 'Reason for failure (optional)',
        placeHolder: 'e.g., Could not find the relevant file'
    });

    await updateRequestStatus(currentRequestId, 'failed', reason || 'Failed via VS Code');
    log(`Request ${currentRequestId.substring(0, 8)}... marked as failed`);
    vscode.window.showWarningMessage('Request marked as failed');
    currentRequestId = undefined;
    updateStatusBar('polling');
}

async function updateRequestStatus(requestId, status, result) {
    try {
        await apiPut(`/api/vscode/requests/${requestId}`, { status, result });
    } catch (err) {
        log(`Failed to update status: ${err.message}`);
    }
}

// ============================================================================
// Queue display
// ============================================================================

async function showQueue() {
    try {
        const data = await apiGet('/api/vscode/requests');

        if (!data.success || !data.requests || data.requests.length === 0) {
            vscode.window.showInformationMessage('Atlas Bridge: No requests in queue');
            return;
        }

        const items = data.requests.map(req => ({
            label: `${statusIcon(req.status)} ${req.message.substring(0, 80)}`,
            description: req.status,
            detail: `ID: ${req.id.substring(0, 8)}... | Created: ${req.created_at}${req.result ? ' | Result: ' + req.result : ''}`,
            request: req
        }));

        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: 'VS Code Bridge Request Queue',
            title: 'Atlas Code Requests'
        });

        if (selected) {
            const doc = await vscode.workspace.openTextDocument({
                content: JSON.stringify(selected.request, null, 2),
                language: 'json'
            });
            await vscode.window.showTextDocument(doc);
        }
    } catch (err) {
        vscode.window.showErrorMessage(`Failed to load queue: ${err.message}`);
    }
}

function statusIcon(status) {
    switch (status) {
        case 'pending': return '$(clock)';
        case 'in_progress': return '$(sync~spin)';
        case 'completed': return '$(check)';
        case 'failed': return '$(error)';
        default: return '$(question)';
    }
}

// ============================================================================
// Status bar
// ============================================================================

function updateStatusBar(state) {
    switch (state) {
        case 'polling':
            statusBarItem.text = '$(radio-tower) Atlas';
            statusBarItem.backgroundColor = undefined;
            break;
        case 'processing':
            statusBarItem.text = '$(sync~spin) Atlas';
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
            break;
        case 'stopped':
            statusBarItem.text = '$(circle-slash) Atlas';
            statusBarItem.backgroundColor = undefined;
            break;
        case 'idle':
            statusBarItem.text = '$(radio-tower) Atlas';
            statusBarItem.backgroundColor = undefined;
            break;
    }
}

// ============================================================================
// HTTP helpers
// ============================================================================

function getBaseUrl() {
    const config = vscode.workspace.getConfiguration('chattyBridge');
    return config.get('apiUrl', 'http://localhost:5001');
}

/**
 * @param {string} path
 * @returns {Promise<any>}
 */
function apiGet(path) {
    return new Promise((resolve, reject) => {
        const url = new URL(path, getBaseUrl());
        const client = url.protocol === 'https:' ? https : http;

        const req = client.get(url.toString(), { timeout: 5000 }, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(body));
                } catch {
                    reject(new Error(`Invalid JSON: ${body.substring(0, 100)}`));
                }
            });
        });

        req.on('error', reject);
        req.on('timeout', () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });
    });
}

/**
 * @param {string} path
 * @param {object} data
 * @returns {Promise<any>}
 */
function apiPut(path, data) {
    return apiRequest(path, 'PUT', data);
}

/**
 * @param {string} path
 * @param {object} data
 * @returns {Promise<any>}
 */
function apiPost(path, data) {
    return apiRequest(path, 'POST', data);
}

/**
 * @param {string} path
 * @param {string} method
 * @param {object} data
 * @returns {Promise<any>}
 */
function apiRequest(path, method, data) {
    return new Promise((resolve, reject) => {
        const url = new URL(path, getBaseUrl());
        const client = url.protocol === 'https:' ? https : http;
        const payload = JSON.stringify(data);

        const req = client.request(url.toString(), {
            method,
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(payload)
            },
            timeout: 5000
        }, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(body));
                } catch {
                    reject(new Error(`Invalid JSON: ${body.substring(0, 100)}`));
                }
            });
        });

        req.on('error', reject);
        req.on('timeout', () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });

        req.write(payload);
        req.end();
    });
}

// ============================================================================
// Logging
// ============================================================================

function log(message) {
    const timestamp = new Date().toISOString();
    outputChannel.appendLine(`[${timestamp}] ${message}`);
}

module.exports = { activate, deactivate };
