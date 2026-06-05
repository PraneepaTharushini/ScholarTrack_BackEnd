import os
import uuid
import asyncio
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from pydantic import BaseModel, Field
from typing import Literal
from PIL import Image
import pytesseract
from pypdf import PdfReader
from database import get_connection

# ── Tesseract Configuration ──────────────────────────────────
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
else:
    print(f"Warning: Tesseract not found at '{TESSERACT_CMD}'.")

# ── Google AI SDK Setup ──────────────────────────────────────
HAS_ANTIGRAVITY = False
try:
    from google.antigravity import Agent, LocalAgentConfig
    HAS_ANTIGRAVITY = True
    print("Google Antigravity SDK loaded.")
except ImportError:
    print("Google Antigravity SDK not found. Using google-genai fallback.")

HAS_GENAI = False
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    print("Warning: google-genai SDK not installed.")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ocr_bp = Blueprint("ocr", __name__)


# ==========================================
# Pydantic Models
# ==========================================

class AIAnalysis(BaseModel):
    urgency_score: int = Field(..., description="Task urgency score from 1 to 10.")
    importance_score: int = Field(..., description="Task importance score from 1 to 10.")
    recommended_priority: Literal["Low", "Medium", "High"] = Field(..., description="Priority: Low, Medium, or High.")

class TaskDetails(BaseModel):
    task_title: str = Field(..., description="Specific academic task/assignment title.")
    subject: str = Field(..., description="Academic subject or course name.")
    deadline: str = Field(..., description="Cleanly formatted deadline date.")
    status: Literal["Pending", "Completed", "In Progress"] = Field("Pending")
    source: str = Field(..., description="Source descriptor detailing file type.")
    description: str = Field(..., description="Comprehensive details and instructions.")
    ai_analysis: AIAnalysis = Field(..., description="AI analysis block.")


# ==========================================
# Helper Functions
# ==========================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_image(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in {'png', 'jpg', 'jpeg'}

def extract_text_from_image(file_path):
    try:
        with Image.open(file_path) as img:
            return pytesseract.image_to_string(img).strip()
    except Exception as e:
        raise RuntimeError(f"Tesseract OCR failed: {str(e)}")

def extract_text_from_pdf(file_path):
    try:
        reader = PdfReader(file_path)
        texts = [page.extract_text() for page in reader.pages if page.extract_text()]
        return "\n".join(texts).strip()
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {str(e)}")

def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

async def run_antigravity_agent(prompt: str):
    config = LocalAgentConfig()
    async with Agent(config) as agent:
        response = await agent.chat(prompt)
        return response.structured_output(TaskDetails)

def init_ocr_tables():
    """Create documents table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id          SERIAL PRIMARY KEY,
                filename    TEXT NOT NULL,
                status      TEXT DEFAULT 'Uploaded',
                path        TEXT,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)
    print("OCR tables ready.")


# ==========================================
# Routes
# ==========================================

@ocr_bp.route("/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Only PDF, JPG, PNG, JPEG supported."}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                INSERT INTO documents (filename, status, path)
                VALUES (%s, 'Uploaded', %s)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (filename, file_path)
            ).fetchone()
            doc_id = row["id"] if row else None

        return jsonify({
            "message": "File uploaded successfully.",
            "document": {"id": doc_id, "filename": filename, "status": "Uploaded"}
        }), 201

    except Exception as e:
        return jsonify({"error": f"DB error: {str(e)}"}), 500


@ocr_bp.route("/task-details", methods=["POST"])
def get_task_details():
    if not os.getenv("GEMINI_API_KEY"):
        return jsonify({"error": "GEMINI_API_KEY is not set in .env"}), 500

    data = request.get_json() or {}
    filename = data.get("filename")

    if not filename:
        return jsonify({"error": "Missing 'filename' in request body"}), 400

    file_path = None
    try:
        with get_connection() as conn:
            doc = conn.execute(
                "SELECT * FROM documents WHERE filename = %s", (filename,)
            ).fetchone()

            if doc:
                file_path = doc["path"]
                conn.execute(
                    "UPDATE documents SET status = 'Processing' WHERE filename = %s", (filename,)
                )
            else:
                potential_path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
                if os.path.exists(potential_path):
                    file_path = potential_path
                    conn.execute(
                        "INSERT INTO documents (filename, status, path) VALUES (%s, 'Processing', %s)",
                        (filename, file_path)
                    )
    except Exception as e:
        return jsonify({"error": f"DB error: {str(e)}"}), 500

    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": f"File '{filename}' not found. Please upload it first."}), 404

    # Extract text
    try:
        if is_image(filename):
            raw_text = extract_text_from_image(file_path)
            source_desc = f"Extracted from Image ({filename})"
        else:
            raw_text = extract_text_from_pdf(file_path)
            source_desc = f"Extracted from PDF ({filename})"
            if not raw_text.strip():
                return jsonify({"error": "PDF has no digital text."}), 422
    except Exception as e:
        return jsonify({"error": f"Extraction failed: {str(e)}"}), 500

    if not raw_text.strip():
        return jsonify({"error": "No readable text extracted."}), 422

    prompt = (
        f"You are Scholar-Track's specialized academic agent. Analyze the following messy raw text "
        f"extracted from an academic syllabus, notice, or course outline. Parse and structure the details "
        f"into a clean JSON schema.\n\n"
        f"- task_title: Extract the clear name of the task/assignment.\n"
        f"- subject: Extract the course or subject name.\n"
        f"- deadline: Format as 'DD Month YYYY'.\n"
        f"- status: Default to 'Pending'.\n"
        f"- source: Set as '{source_desc}'.\n"
        f"- description: Concise summary of what needs to be done.\n"
        f"- ai_analysis: urgency (1-10), importance (1-10), recommended priority (Low/Medium/High).\n\n"
        f"Raw Text:\n{raw_text}"
    )

    try:
        task_data = None

        if HAS_ANTIGRAVITY:
            try:
                task_data = run_async(run_antigravity_agent(prompt))
            except Exception as err:
                print(f"Antigravity error: {err}. Falling back to genai.")

        if not task_data:
            if not HAS_GENAI:
                raise RuntimeError("No AI SDK available.")
            client = genai.Client()
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TaskDetails,
                    temperature=0.1,
                )
            )
            task_data = TaskDetails.model_validate_json(response.text)

        with get_connection() as conn:
            conn.execute(
                "UPDATE documents SET status = 'Processed' WHERE filename = %s", (filename,)
            )

        return jsonify(task_data.model_dump()), 200

    except Exception as e:
        with get_connection() as conn:
            conn.execute(
                "UPDATE documents SET status = 'Failed' WHERE filename = %s", (filename,)
            )
        return jsonify({"error": f"AI parsing failed: {str(e)}"}), 500


@ocr_bp.route("/documents", methods=["GET"])
def get_documents():
    try:
        with get_connection() as conn:
            docs = conn.execute(
                "SELECT id, filename, status FROM documents ORDER BY created_at DESC"
            ).fetchall()
        return jsonify({"documents": [dict(d) for d in docs]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500