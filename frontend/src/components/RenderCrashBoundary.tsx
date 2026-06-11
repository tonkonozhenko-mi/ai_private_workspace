import { Component, type ErrorInfo, type ReactNode } from "react";

interface RenderCrashBoundaryProps {
  title: string;
  children: ReactNode;
}

interface RenderCrashBoundaryState {
  errorMessage: string | null;
}

export class RenderCrashBoundary extends Component<
  RenderCrashBoundaryProps,
  RenderCrashBoundaryState
> {
  state: RenderCrashBoundaryState = { errorMessage: null };

  static getDerivedStateFromError(error: Error): RenderCrashBoundaryState {
    return { errorMessage: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`${this.props.title} failed to render`, error, info);
  }

  render() {
    if (this.state.errorMessage) {
      return (
        <section className="panel render-crash-panel">
          <p className="eyebrow">Recovery</p>
          <h2>{this.props.title}</h2>
          <p>
            This screen hit a UI rendering issue, but the rest of the workspace
            can keep running. The backend data stayed read-only and unchanged.
          </p>
          <code>{this.state.errorMessage}</code>
        </section>
      );
    }

    return this.props.children;
  }
}
