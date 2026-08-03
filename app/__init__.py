"""Flask application factory for the Multi-Agent Parking Simulation dashboard."""
import os
from flask import Flask


def create_app():
    """Create and configure the Flask application."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
    app.config["OUTPUT_DIR"] = os.environ.get(
        "SIM_OUTPUT_DIR", os.path.join(base_dir, "output")
    )
    app.config["BASE_DIR"] = base_dir

    from app import routes  # noqa: E402

    app.register_blueprint(routes.bp)

    return app
