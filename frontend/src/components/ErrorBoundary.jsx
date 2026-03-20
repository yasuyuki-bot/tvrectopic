import React from 'react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true };
    }

    componentDidCatch(error, errorInfo) {
        console.error("ErrorBoundary caught an error", error, errorInfo);
        this.setState({ error, errorInfo });
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 text-white p-8">
                    <div className="max-w-2xl w-full bg-gray-900 p-6 rounded-xl border border-red-500">
                        <h2 className="text-xl font-bold text-red-400 mb-4">Something went wrong</h2>
                        <div className="bg-black p-4 rounded overflow-auto mb-4 font-mono text-sm h-64">
                            <p className="text-red-300 font-bold mb-2">{this.state.error && this.state.error.toString()}</p>
                            <pre className="text-gray-400">{this.state.errorInfo && this.state.errorInfo.componentStack}</pre>
                        </div>
                        <button
                            onClick={this.props.onClose}
                            className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded text-white"
                        >
                            Close
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
