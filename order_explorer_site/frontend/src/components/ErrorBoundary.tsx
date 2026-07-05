import { Component } from 'react';
import type { ErrorInfo, PropsWithChildren } from 'react';

interface State {
  error: Error | null;
}

class ErrorBoundary extends Component<PropsWithChildren, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled UI error:', error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 px-6 text-center">
          <h2 className="font-display text-lg font-semibold text-ink">Something went wrong</h2>
          <p className="max-w-md text-sm text-muted">{this.state.error.message || 'An unexpected error occurred.'}</p>
          <button
            type="button"
            onClick={this.handleReset}
            className="rounded-lg bg-signal px-4 py-2 text-sm font-medium text-white"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
