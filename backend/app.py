"""Birthday Chronicles application entry point."""

from backend.web.app import app


def main():
    """Run the Birthday Chronicles development server."""
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000,
    )


if __name__ == "__main__":
    main()
