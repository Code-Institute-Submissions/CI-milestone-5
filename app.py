import os
from datetime import date, datetime
from flask import (Flask, flash, render_template,
                   redirect, request, session, url_for)
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from google.cloud import storage
if os.path.exists("env.py"):
    import env


app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)
CLOUD_STORAGE_BUCKET = os.environ.get("CLOUD_STORAGE_BUCKET")


# Displays all posted brews
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
        return redirect(url_for("profile", username=session["user"]))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Check if username exists
        user = mongo.db.Users.find_one(
            {"username": request.form.get("username").lower()})

        if user:
            # Check hashed password for user
            if check_password_hash(
                    user["password"], request.form.get("password")):
                session["user"] = request.form.get("username").lower()
                flash("Welcome, {}".format(request.form.get("username")))
                return redirect(url_for("profile", username=session["user"]))
            else:
                # If password is invalid
                flash("Incorrect Username and/or Password")

        else:
            # username doesn't exist
            flash("Incorrect Username and/or Password")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/user/<username>", methods=["GET", "POST"])
def profile(username):
    # Retrieve user in session from database
    username = mongo.db.Users.find_one(
        {"username": session["user"]})["username"]
    brews = mongo.db.Brews.find({"created_by": username}).sort("_id", -1).limit(6)

    if session["user"]:
        return render_template("profile.html", username=username, brews=brews)

    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    # remove user from session
    flash("You have logged out")
    session.pop("user")
    return redirect("login")


@app.route("/search", methods=["GET", "POST"])
def search():
    query = request.form.get("search")
    brews = mongo.db.Brews.find({"$text": {"$search": query}})
    return render_template("brews.html", brews=brews)


@app.route("/new_brew", methods=["GET", "POST"])
def new_brew():
    if request.method == "POST":
        date = datetime.now()

        # Retrieve uploaded image
        image_file = request.files.get("image")
        image_url = ""

        if image_file:
            # Send to Google Cloud Storage bucket
            gcs = storage.Client()
            bucket = gcs.get_bucket(CLOUD_STORAGE_BUCKET)
            blob = bucket.blob(image_file.filename)
            blob.upload_from_string(
                image_file.read(),
                content_type=image_file.content_type
            )
            blob.make_public()
            image_url = blob.public_url

        brew = {
            "name": request.form.get("name"),
            "description": request.form.get("description"),
            "flavour": request.form.get("flavour"),
            "image_url": image_url,
            "created_by": session["user"],
            "created_on": date.strftime("%d/%m/%y")
        }
        mongo.db.Brews.insert_one(brew)
        flash("Brew added!")

    flavours = mongo.db.Flavours.find().sort("flavour_name", 1)
    return render_template("new_brew.html", flavours=flavours)


@app.route("/brew/<id>")
def brew(id):
    brew = mongo.db.Brews.find_one({"_id": ObjectId(id)})
    comments = mongo.db.Comments.find({"brew_id": ObjectId(id)})

    return render_template("brew.html", brew=brew, comments=comments)


@app.route("/edit_brew/<id>", methods=["GET", "POST"])
def edit_brew(id):
    if request.method == "POST":
        edited_brew = {
            "name": request.form.get("name"),
            "description": request.form.get("description"),
            "flavour": request.form.get("flavour"),
            "created_by": session["user"],
        }
        mongo.db.Brews.update_one({"_id": ObjectId(id)}, {"$set": edited_brew})
        flash("Brew edited!")
        return redirect(url_for("brew", id=id))

    brew = mongo.db.Brews.find_one({"_id": ObjectId(id)})
    flavours = mongo.db.Flavours.find().sort("flavour_name", 1)

    return render_template("edit_brew.html", brew=brew, flavours=flavours)


@app.route("/delete_brew/<id>")
def delete_brew(id):
    mongo.db.Brews.delete_one({"_id": ObjectId(id)})
    flash("Brew removed!")

    return redirect(url_for("get_brews"))


@app.route("/post_comment/<brew_id>", methods=["POST"])
def post_comment(brew_id):
    date = datetime.now()
    comment = {
        "text": request.form.get("comment"),
        "created_by": session["user"],
        "created_on": date.strftime("%d/%m/%y"),
        "brew_id": ObjectId(brew_id)
    }
    mongo.db.Comments.insert_one(comment)
    flash("Comment posted!")

    return redirect(url_for("brew", id=brew_id))


@app.route("/delete_comment/<brew_id>/<id>")
def delete_comment(id, brew_id):
    mongo.db.Comments.delete_one({"_id": ObjectId(id)})
    flash("Comment removed!")

    return redirect(url_for("brew", id=brew_id))


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)
