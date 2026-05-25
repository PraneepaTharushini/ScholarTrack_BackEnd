"""
scholar_track_priority
======================
Self-contained Flask module for task priority scoring and recommendations.

To register in your main Flask app:

    from scholar_track_priority import register_priority_module
    register_priority_module(app)

All routes will be available under  /api/priority/
"""

from .routes.priority_routes import priority_bp


def register_priority_module(app):
    """
    Register the priority blueprint with the Flask application.

    Call this in your create_app() factory function AFTER initialising db.

    Example:
        def create_app():
            app = Flask(__name__)
            app.config.from_object(Config)
            db.init_app(app)

            from scholar_track_priority import register_priority_module
            register_priority_module(app)

            return app
    """
    app.register_blueprint(priority_bp, url_prefix="/api/priority")


__all__ = ["priority_bp", "register_priority_module"]
