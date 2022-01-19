import os
from flask import (Flask, flash, render_template,
                   redirect, request, session, url_for)
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
if os.path.exists("env.py"):
    import env


app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)


@app.route("/")
@app.route("/get_brews")
def get_brews():
    brews = mongo.db.Brews.find()
    return render_template("brews.html", brews=brews)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Check if username exists
        user = mongo.db.Users.find_one(
            {"username": request.form.get("username").lower()})
        
        if user:
            flash("Username already exists")
            return redirect(url_for("register"))
        
        register = {
            "username": request.form.get("username").lower(),
            "password": generate_password_hash(request.form.get("password"))
        }
        mongo.db.Users.insert_one(register)

        # Add new user to session
        session["user"] = request.form.get("username").lower()
        flash("Registration successful!")

    return render_template("register.html")


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)
