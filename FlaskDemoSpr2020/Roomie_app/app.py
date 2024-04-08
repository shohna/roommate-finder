from flask import Flask, render_template, request, session, redirect, url_for, flash
import psycopg2

app = Flask(__name__)
app.secret_key = 'secret'


db_params = {
    'host': 'database-1.cxeumckggdgy.us-east-2.rds.amazonaws.com',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'pdscsgy1234',
}
conn = psycopg2.connect(**db_params)

# Routes
@app.route('/')
def index():    # Establish a connection to the PostgreSQL database
    # Create a cursor object
    cursor = conn.cursor()
    # Execute a sample SQL query
    cursor.execute('SELECT version()')
    # Fetch the result
    db_version = cursor.fetchone()[0]
    # Close cursor and connection
    cursor.close()
    # Return the database version as a response
    return f'Database Version: {db_version}'
    # return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Verify login credentials
        cursor = conn.cursor()
        query = 'SELECT * FROM Users WHERE username = %s AND passwd = %s'
        cursor.execute(query, (username, password))
        user = cursor.fetchone()
        cursor.close()
        if user:
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        dob = request.form['dob']
        gender = request.form['gender']
        email = request.form['email']
        phone = request.form['phone']
        # Add registration details to the Users table
        cursor = conn.cursor()
        query = 'INSERT INTO Users (username, passwd, first_name, last_name, DOB, gender, email, Phone) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'
        cursor.execute(query, (username, password, first_name, last_name, dob, gender, email, phone))
        conn.commit()
        cursor.close()
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

# @app.route('/home')
# def home():
#     if 'username' in session:
#         username = session['username']
#         return render_template('home.html', username=username)
#     else:
#         return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'username' in session:
        username = session['username']
        return render_template('home.html', username=username)
    else:
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))


@app.route('/search_units', methods=['GET'])
def search_units():
    building_name = request.args.get('building_name')
    company_name = request.args.get('company_name')
    cursor = conn.cursor()
    query = 'SELECT * FROM ApartmentUnit WHERE CompanyName = %s AND BuildingName = %s'
    cursor.execute(query, (company_name, building_name))
    units = cursor.fetchall()
    cursor.close()
    return render_template('home.html', username=session['username'], units=units)


@app.route('/search_units_by_pet', methods=['GET'])
def search_units_by_pet():
    pet_name = request.args.get('pet_name')
    cursor = conn.cursor()
    query = '''
        SELECT AU.*, PP.isAllowed AS pet_allowed
        FROM ApartmentUnit AU
        JOIN PetPolicy PP ON AU.CompanyName = PP.CompanyName AND AU.BuildingName = PP.BuildingName
        JOIN Pets P ON P.username = %s AND PP.PetType = P.PetType AND PP.PetSize = P.PetSize
        WHERE AU.UnitRentID IN (
            SELECT AU.UnitRentID
            FROM ApartmentUnit AU
            JOIN PetPolicy PP ON AU.CompanyName = PP.CompanyName AND AU.BuildingName = PP.BuildingName
            JOIN Pets P ON P.username = %s AND PP.PetType = P.PetType AND PP.PetSize = P.PetSize
            WHERE P.PetName = %s AND PP.isAllowed = 1
        )
    '''
    # cursor.execute(query, (session['username'], pet_name))
    cursor.execute(query, (session['username'], session['username'], pet_name))
    units = cursor.fetchall()
    cursor.close()
    error_message = 'No matching apartment units found. Please check your input and try again.' if not units else None
    return render_template('home.html', username=session['username'], units=units, error_message=error_message)

@app.route('/unit_building_info', methods=['GET'])
def unit_building_info():
    print("hi2")
    if 'username' in session:
        print("hi")
        unit_id = request.args.get('unit_id')
        cursor = conn.cursor()
        query = '''
        SELECT AU.*, AB.*, STRING_AGG(AI.aType, ', ') AS amenities
        FROM ApartmentUnit AU
        JOIN ApartmentBuilding AB ON AU.CompanyName = AB.CompanyName AND AU.BuildingName = AB.BuildingName
        LEFT JOIN AmenitiesIn AI ON AU.UnitRentID = AI.UnitRentID
        WHERE AU.UnitRentID = %s
        GROUP BY AU.UnitRentID, AU.CompanyName, AU.BuildingName, AB.CompanyName, AB.BuildingName
        '''
        print("hi3")
        cursor.execute(query, (unit_id,))
        unit_info = cursor.fetchone()
        cursor.close()
        print("hi4")
        if unit_info:
            print(unit_info)
            print("hi5")
            return render_template('unit_building_info.html', unit_info=unit_info)
        else:
            print("hi6")
            flash('Unit not found')
            return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)