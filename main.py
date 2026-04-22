from flask import Flask, render_template, request, redirect, session, jsonify
from supabase import create_client
import os
from dotenv import load_dotenv
import hashlib

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "assivo_secret_2026")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "assivo.agency@gmail.com")
ADMIN_PASS  = os.environ.get("ADMIN_PASS", "admin")

def sb():
    return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY"))

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


# --- AUTH ---
@app.route("/")
def index():
    if "user" not in session:
        return redirect("/login")
    if session.get("is_admin"):
        return redirect("/admin")
    return redirect("/dashboard")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        pw    = request.form.get("wachtwoord")
        if email == ADMIN_EMAIL and pw == ADMIN_PASS:
            session["user"] = email
            session["is_admin"] = True
            return redirect("/admin")
        result = sb().table("klanten").select("*").eq("email", email).eq("wachtwoord", hash_pw(pw)).execute()
        if result.data:
            session["user"] = email
            session["is_admin"] = False
            session["klant_id"] = result.data[0]["id"]
            session["klant_naam"] = result.data[0]["naam"]
            return redirect("/dashboard")
        error = "Verkeerd emailadres of wachtwoord."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# --- ADMIN ---
@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect("/login")
    klanten  = sb().table("klanten").select("*").execute().data
    projecten = sb().table("projecten").select("*").order("created_at", desc=True).execute().data
    return render_template("admin.html", klanten=klanten, projecten=projecten)

@app.route("/admin/klant/nieuw", methods=["POST"])
def nieuw_klant():
    if not session.get("is_admin"):
        return redirect("/login")
    naam  = request.form.get("naam")
    email = request.form.get("email")
    pw    = request.form.get("wachtwoord")
    sb().table("klanten").insert({"naam": naam, "email": email, "wachtwoord": hash_pw(pw)}).execute()
    return redirect("/admin")

@app.route("/admin/project/nieuw", methods=["POST"])
def nieuw_project():
    if not session.get("is_admin"):
        return redirect("/login")
    sb().table("projecten").insert({
        "klant_id":    int(request.form.get("klant_id")),
        "naam":        request.form.get("naam"),
        "status":      request.form.get("status"),
        "beschrijving": request.form.get("beschrijving")
    }).execute()
    return redirect("/admin")

@app.route("/admin/project/<int:project_id>")
def admin_project(project_id):
    if not session.get("is_admin"):
        return redirect("/login")
    project  = sb().table("projecten").select("*").eq("id", project_id).execute().data[0]
    taken    = sb().table("taken").select("*").eq("project_id", project_id).execute().data
    berichten = sb().table("berichten").select("*").eq("project_id", project_id).order("created_at").execute().data
    klanten  = sb().table("klanten").select("*").execute().data
    return render_template("project.html", project=project, taken=taken, berichten=berichten, klanten=klanten, is_admin=True)

@app.route("/admin/project/<int:project_id>/status", methods=["POST"])
def update_status(project_id):
    if not session.get("is_admin"):
        return redirect("/login")
    sb().table("projecten").update({"status": request.form.get("status")}).eq("id", project_id).execute()
    return redirect(f"/admin/project/{project_id}")

@app.route("/admin/project/<int:project_id>/taak", methods=["POST"])
def add_taak(project_id):
    if not session.get("is_admin"):
        return redirect("/login")
    sb().table("taken").insert({
        "project_id": project_id,
        "naam":       request.form.get("naam"),
        "deadline":   request.form.get("deadline")
    }).execute()
    return redirect(f"/admin/project/{project_id}")

@app.route("/admin/taak/<int:taak_id>/status", methods=["POST"])
def update_taak(taak_id):
    if not session.get("is_admin"):
        return redirect("/login")
    data = request.get_json()
    project_id = data.get("project_id")
    sb().table("taken").update({"status": data.get("status")}).eq("id", taak_id).execute()
    return jsonify({"ok": True})

@app.route("/admin/project/<int:project_id>/bericht", methods=["POST"])
def admin_bericht(project_id):
    if not session.get("is_admin"):
        return redirect("/login")
    sb().table("berichten").insert({"project_id": project_id, "tekst": request.form.get("tekst"), "van_admin": True}).execute()
    return redirect(f"/admin/project/{project_id}")


# --- KLANT ---
@app.route("/dashboard")
def dashboard():
    if "user" not in session or session.get("is_admin"):
        return redirect("/login")
    projecten = sb().table("projecten").select("*").eq("klant_id", session["klant_id"]).execute().data
    return render_template("dashboard.html", naam=session["klant_naam"], projecten=projecten)

@app.route("/project/<int:project_id>")
def klant_project(project_id):
    if "user" not in session or session.get("is_admin"):
        return redirect("/login")
    project   = sb().table("projecten").select("*").eq("id", project_id).eq("klant_id", session["klant_id"]).execute().data
    if not project:
        return redirect("/dashboard")
    taken     = sb().table("taken").select("*").eq("project_id", project_id).execute().data
    berichten = sb().table("berichten").select("*").eq("project_id", project_id).order("created_at").execute().data
    return render_template("project.html", project=project[0], taken=taken, berichten=berichten, is_admin=False)

@app.route("/project/<int:project_id>/bericht", methods=["POST"])
def klant_bericht(project_id):
    if "user" not in session or session.get("is_admin"):
        return redirect("/login")
    sb().table("berichten").insert({"project_id": project_id, "tekst": request.form.get("tekst"), "van_admin": False}).execute()
    return redirect(f"/project/{project_id}")


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5003)))
