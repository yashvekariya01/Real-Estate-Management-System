from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "realestatekey"
app.config['UPLOAD_FOLDER'] = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="realestate_test"
)
cursor = db.cursor()

# ---------- HELPER FUNCTIONS ----------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------- ROUTES ----------

@app.route('/')
def index():
    cursor.execute("SELECT * FROM properties")
    properties = cursor.fetchall()
    return render_template('index.html', properties=properties)


@app.route('/filter', methods=['GET'])
def filter_properties():
    query = "SELECT * FROM properties WHERE 1=1"
    params = []

    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')
    ptype = request.args.get('type')
    status = request.args.get('status')

    if min_price:
        query += " AND price >= %s"
        params.append(min_price)
    if max_price:
        query += " AND price <= %s"
        params.append(max_price)
    if ptype:
        query += " AND type = %s"
        params.append(ptype)
    if status:
        query += " AND status = %s"
        params.append(status)

    cursor.execute(query, tuple(params))
    properties = cursor.fetchall()
    return render_template('filter_properties.html', properties=properties)


@app.route('/property/<int:id>')
def property_detail(id):
    cursor.execute("SELECT * FROM properties WHERE id=%s", (id,))
    property_data = cursor.fetchone()
    return render_template('property_detail.html', property=property_data)


@app.route('/save_property/<int:property_id>', methods=['POST'])
def save_property(property_id):
    if not session.get('user_id'):
        return redirect('/login')
    user_id = session['user_id']
    cursor.execute("SELECT * FROM saved_properties WHERE user_id=%s AND property_id=%s", (user_id, property_id))
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("INSERT INTO saved_properties (user_id, property_id) VALUES (%s, %s)", (user_id, property_id))
        db.commit()
    return redirect(f'/property/{property_id}')


@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect('/')
    cursor.execute("SELECT * FROM properties")
    properties = cursor.fetchall()
    return render_template('admin_dashboard.html', properties=properties)


@app.route('/add', methods=['GET', 'POST'])
def add_property():
    if session.get('role') != 'admin':
        return redirect('/')

    if request.method == 'POST':
        data = request.form
        image = request.files['image']

        # Validation
        required_fields = ['name', 'location', 'price', 'type', 'description',
                           'bedrooms', 'bathrooms', 'area_sqft', 'status',
                           'year_built', 'contact_number']
        for field in required_fields:
            if not data.get(field):
                flash(f"{field.replace('_', ' ').title()} is required.")
                return redirect('/add')

        # Price check
        try:
            price = float(data['price'])
            if price <= 0:
                flash("Price must be greater than 0.")
                return redirect('/add')
        except ValueError:
            flash("Invalid price.")
            return redirect('/add')

        # Image check
        if image.filename == '':
            flash("Image is required.")
            return redirect('/add')
        if not allowed_file(image.filename):
            flash("Invalid image file. Allowed types: png, jpg, jpeg, gif.")
            return redirect('/add')

        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # Insert into DB
        cursor.execute("""
            INSERT INTO properties
            (property_name, location, price, type, description, bedrooms, bathrooms, area_sqft, status, year_built, contact_number, image)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data['name'], data['location'], price, data['type'], data['description'],
            data['bedrooms'], data['bathrooms'], data['area_sqft'], data['status'],
            data['year_built'], data['contact_number'], filename
        ))
        db.commit()
        flash("Property added successfully.")
        return redirect('/admin/dashboard')

    return render_template('add_property.html')


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_property(id):
    if session.get('role') != 'admin':
        return redirect('/')

    if request.method == 'POST':
        data = request.form
        if 'image' in request.files and request.files['image'].filename != '':
            image = request.files['image']
            if not allowed_file(image.filename):
                flash("Invalid image file.")
                return redirect(f'/edit/{id}')
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cursor.execute("""
                UPDATE properties SET property_name=%s, location=%s, price=%s, type=%s, description=%s,
                bedrooms=%s, bathrooms=%s, area_sqft=%s, status=%s, year_built=%s, contact_number=%s, image=%s
                WHERE id=%s
            """, (
                data['name'], data['location'], data['price'], data['type'], data['description'],
                data['bedrooms'], data['bathrooms'], data['area_sqft'], data['status'],
                data['year_built'], data['contact_number'], filename, id
            ))
        else:
            cursor.execute("""
                UPDATE properties SET property_name=%s, location=%s, price=%s, type=%s, description=%s,
                bedrooms=%s, bathrooms=%s, area_sqft=%s, status=%s, year_built=%s, contact_number=%s
                WHERE id=%s
            """, (
                data['name'], data['location'], data['price'], data['type'], data['description'],
                data['bedrooms'], data['bathrooms'], data['area_sqft'], data['status'],
                data['year_built'], data['contact_number'], id
            ))
        db.commit()
        flash("Property updated successfully.")
        return redirect('/admin/dashboard')

    cursor.execute("SELECT * FROM properties WHERE id=%s", (id,))
    property_data = cursor.fetchone()
    return render_template('edit_property.html', property=property_data)


@app.route('/delete/<int:id>')
def delete_property(id):
    if session.get('role') != 'admin':
        return redirect('/')
    cursor.execute("DELETE FROM properties WHERE id=%s", (id,))
    db.commit()
    flash("Property deleted successfully.")
    return redirect('/admin/dashboard')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        pwd = request.form['password'].strip()

        if not email or not pwd:
            flash("Email and password are required.")
            return redirect('/login')

        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, pwd))
        user = cursor.fetchone()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[4]
            if user[4] == 'admin':
                return redirect('/admin/dashboard')
            else:
                return redirect('/')
        else:
            flash("Invalid email or password")
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        uname = request.form['username']
        email = request.form['email']
        pwd = request.form['password']
        if not uname or not email or not pwd:
            flash("All fields are required.")
            return redirect('/signup')
        cursor.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, 'user')", (uname, email, pwd))
        db.commit()
        flash("Signup successful. Please login.")
        return redirect('/login')
    return render_template('signup.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect('/')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash("Thank you for contacting us. We will get back to you soon!")
        return redirect('/contact')
    return render_template('contact.html')


@app.route('/saved_properties')
def saved_properties():
    if not session.get('user_id'):
        return redirect('/login')

    user_id = session['user_id']
    query = """
        SELECT p.id, p.property_name, p.location, p.price, p.type, p.description, 
               p.bedrooms, p.bathrooms, p.area_sqft, p.status, p.year_built, 
               p.contact_number, p.image
        FROM saved_properties sp
        JOIN properties p ON sp.property_id = p.id
        WHERE sp.user_id = %s
    """
    cursor.execute(query, (user_id,))
    properties = cursor.fetchall()
    return render_template('saved_properties.html', properties=properties)


@app.route('/delete_saved_property/<int:property_id>')
def delete_saved_property(property_id):
    if not session.get('user_id'):
        return redirect('/login')
    user_id = session['user_id']
    cursor.execute("DELETE FROM saved_properties WHERE user_id=%s AND property_id=%s", (user_id, property_id))
    db.commit()
    flash("Property removed from saved list.")
    return redirect('/saved_properties')


if __name__ == "__main__":
    app.run(debug=True)
