from .routes.priority_routes import priority_bp


def register_priority_module(app):
    """
    Call this in your create_app() after db.init_app(app):

        from scholar_track_priority import register_priority_module
        register_priority_module(app)
    """
    app.register_blueprint(priority_bp, url_prefix="/api/priority")


__all__ = ["priority_bp", "register_priority_module"]
