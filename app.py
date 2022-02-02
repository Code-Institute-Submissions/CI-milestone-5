import os
from datetime import date, datetime
from functools import wraps
from flask import (abort, Flask, flash, render_template,
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


def authenticated(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            session["user"]
            return function(*args, **kwargs)
        except:
            return redirect(url_for("login"))

    return wrapper


def unauthenticated(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            session["user"]
            return redirect(url_for("profile"))
        except:
            return function(*args, **kwargs)

    return wrapper


# Displays all posted brews
@app.route("/")
@app.route("/get_brews")
def get_brews():
    """Returns list of posted brews"""
    brews = mongo.db.Brews.find().sort("_id", -1).limit(25)
    return render_template("brews.html", brews=brews)


@app.route("/register", methods=["GET", "POST"])
@unauthenticated
def register():
    """Returns and processes form for user registration"""
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
        return redirect(url_for("profile"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
@unauthenticated
def login():
    """Returns and processes form for user login"""
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
                return redirect(url_for("profile"))
            else:
                # If password is invalid
                flash("Incorrect Username and/or Password")

        else:
            # username doesn't exist
            flash("Incorrect Username and/or Password")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/my_profile", methods=["GET", "POST"])
@authenticated
def profile():
    """Returns profile template for currently logged in user"""
    # Retrieve Brews posted by session user
    brews = mongo.db.Brews.find(
        {"created_by": session["user"]}).sort("_id", -1).limit(25)

    return render_template("profile.html", brews=brews)


@app.route("/logout")
@authenticated
def logout():
    """Removes user cookies from session, logging user out"""
    # remove user from session
    session.pop("user")
    flash("You have logged out")

    return redirect("login")


@app.route("/search", methods=["GET", "POST"])
def search():
    """Returns brews template with brews from search query"""
    # Using premade index in the mongo database search Brew titles and descriptions
    query = request.form.get("search")
    brews = mongo.db.Brews.find({"$text": {"$search": query}})

    return render_template("brews.html", brews=brews)


@app.route("/new_brew", methods=["GET", "POST"])
@authenticated
def new_brew():
    """Returns and processes form for brew post creation"""
    if request.method == "POST":
        # Create date object for current time
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
    """Returns brew template for entered id"""
    # If try fails due to missing resources, throws 404
    try:
        brew = mongo.db.Brews.find_one({"_id": ObjectId(id)})
        comments = mongo.db.Comments.find(
            {"brew_id": ObjectId(id)}).sort("_id", -1).limit(25)

    except:
        abort(404)

    return render_template("brew.html", brew=brew, comments=comments)


@app.route("/edit_brew/<id>", methods=["GET", "POST"])
@authenticated
def edit_brew(id):
    """Returns and processes brew edit form for entered id"""
    # If try fails due to missing resources, 404
    try:
        brew = mongo.db.Brews.find_one({"_id": ObjectId(id)})
        flavours = mongo.db.Flavours.find().sort("flavour_name", 1)

    except:
        abort(404)

    # If the session user isn't the brew's author, 403
    if brew["created_by"] != session["user"]:
        abort(403)

    if request.method == "POST":
        edited_brew = {
            "name": request.form.get("name"),
            "description": request.form.get("description"),
            "flavour": request.form.get("flavour"),
            "created_by": session["user"],
        }
        # Updates brew entry with edited information
        mongo.db.Brews.update_one(
            {"_id": ObjectId(id)}, {"$set": edited_brew})
        flash("Brew edited!")
        return redirect(url_for("brew", id=id))

    return render_template("edit_brew.html", brew=brew, flavours=flavours)


@app.route("/delete_brew/<id>")
@authenticated
def delete_brew(id):
    """Deleted brew with entered id"""
    try:
        brew = mongo.db.Brews.find_one({"_id": ObjectId(id)})

    except:
        abort(404)

    if brew["created_by"] != session["user"]:
        abort(403)

    mongo.db.Brews.delete_one({"_id": ObjectId(id)})
    mongo.db.Comments.delete_many({"brew_id": ObjectId(id)})
    flash("Brew removed!")

    return redirect(url_for("get_brews"))


@app.route("/post_comment/<brew_id>", methods=["POST"])
@authenticated
def post_comment(brew_id):
    """Enters new comment in Comments collection with entered entered brew id"""
    date = datetime.now()

    # Create comment object
    comment = {
        "text": request.form.get("comment"),
        "created_by": session["user"],
        "created_on": date.strftime("%d/%m/%y"),
        "brew_id": ObjectId(brew_id)
    }
    # Insert into Comments collection
    mongo.db.Comments.insert_one(comment)
    flash("Comment posted!")

    return redirect(url_for("brew", id=brew_id))


@app.route("/delete_comment/<brew_id>/<id>")
@authenticated
def delete_comment(id, brew_id):
    """Deletes comment with id from Comments collection, then redirects back to associated brew page"""

    # Delete comment with id from Comments collection
    mongo.db.Comments.delete_one({"_id": ObjectId(id)})
    flash("Comment removed!")

    return redirect(url_for("brew", id=brew_id))


@app.errorhandler(403)
def error_403(e):
    return render_template("403.html"), 403


@app.errorhandler(404)
def error_404(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)
