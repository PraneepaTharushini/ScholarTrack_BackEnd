import os

from flask import Flask, jsonify
from flask_cors import CORS

from extensions import db
from routes import priority_bp


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:lXkbAOtVInUIMHWZFygvINIaKGlspqwJ@tramway.proxy.rlwy.net:33180/railway",
)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

CORS(app)
db.init_app(app)
app.register_blueprint(priority_bp, url_prefix="/api/priority")

print("API ROUTES LOADED")
print("REGISTERED ROUTES:", app.url_map)

print("Trying to connect database...")

try:
    with app.app_context():
        with db.engine.connect():
            print("Database Connected Successfully!")
except Exception as e:
    print("Database Connection Error:")
    print(e)

@app.route('/')
def home():
    return "Flask is running!"

# IMPORTANT ROUTE FOR REACT
@app.route('/api/test')
def test():
    return jsonify({
        "message": "Backend + Database connected successfully!"
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True, use_reloader=False)