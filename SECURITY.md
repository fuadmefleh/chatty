# Security Policy

Chatty is a personal AI assistant that integrates with sensitive accounts
and data (email, banking/Plaid, order history, messages, memory storage).
If you find a security vulnerability, please report it privately rather
than opening a public issue.

## Reporting a vulnerability

Email **fuad.mefleh@gmail.com** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce, or a proof of concept if available
- Which component is affected (core agent, a specific skill, the web
  dashboard, etc.)

You should receive an acknowledgment within a few days. Please allow time
for a fix before any public disclosure.

## Scope notes

- Runtime secrets (`.env`, `skills/gmail/credentials.json`, OAuth tokens,
  anything under `data/` or `memory/`) are never committed to this repo —
  see `.gitignore`. If you find a leaked credential in the repository
  history, treat it as compromised and report it immediately.
- This project is intended to run under your own control with your own
  credentials; it is not designed for multi-tenant or public-facing
  deployment without additional hardening.
