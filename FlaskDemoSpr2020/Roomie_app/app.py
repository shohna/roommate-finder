from flask import Flask, render_template, request, session, redirect, url_for, flash
import psycopg2
import json

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
    print(units)
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
            WHERE P.PetName = %s AND PP.isAllowed = false
        )
    '''
    # cursor.execute(query, (session['username'], pet_name))
    cursor.execute(query, (session['username'], session['username'], pet_name))
    units = cursor.fetchall()
    cursor.close()
    print(units)
    error_message = 'No matching apartment units found. Please check your input and try again.' if not units else None
    return render_template('home.html', username=session['username'], units=units, error_message=error_message)

@app.route('/unit_building_info', methods=['GET'])
def unit_building_info():
    if 'username' in session:
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
        cursor.execute(query, (unit_id,))
        unit_info = cursor.fetchone()
        cursor.close()
        if unit_info:
            return render_template('unit_building_info.html', unit_info=unit_info)
        else:
            flash('Unit not found')
            return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))

# Routes for registering and editing pets
@app.route('/register_pet', methods=['GET', 'POST'])
def register_pet():
    if request.method == 'POST':
        pet_name = request.form['pet_name']
        pet_type = request.form['pet_type']
        pet_size = request.form['pet_size']
        # Add pet registration details to the Pets table
        cursor = conn.cursor()
        query = 'INSERT INTO Pets (username, PetName, PetType, PetSize) VALUES (%s, %s, %s, %s)'
        cursor.execute(query, (session['username'], pet_name, pet_type, pet_size))
        conn.commit()
        cursor.close()
        flash('Pet registration successful.')
        return redirect(url_for('home'))
    return render_template('register_pet.html')

@app.route('/edit_pet/<string:pet_name>', methods=['GET', 'POST'])
def edit_pet(pet_name):
    cursor = conn.cursor()
    print("hi")
    query = "SELECT * FROM Pets WHERE username = %s AND petname ILIKE %s"
    cursor.execute(query, (session.get('username'), pet_name))
    pet_info = cursor.fetchone()
    cursor.close()
    print("hi3")
    print(pet_info)
    if not pet_info:
        flash('Pet not found or you are not authorized to edit this pet.')
        return redirect(url_for('home'))

    if request.method == 'POST':
        new_pet_name = request.form['pet_name']
        pet_type = request.form['pet_type']
        pet_size = request.form['pet_size']
        # Update pet information in the Pets table
        cursor = conn.cursor()
        update_query = 'UPDATE Pets SET PetName = %s, PetType = %s, PetSize = %s WHERE username = %s AND petname = %s'
        cursor.execute(update_query, (new_pet_name, pet_type, pet_size, session['username'], pet_name))
        conn.commit()
        cursor.close()
        flash('Pet information updated.')
        return redirect(url_for('home'))

    return render_template('edit_pet.html', pet_info=pet_info)

@app.route('/search_interest', methods=['GET', 'POST'])
def search_interest():
    if request.method == 'POST':
        move_in_date = request.form['move_in_date']
        roommate_count = request.form['roommate_count']
        cursor = conn.cursor()

        # SQL query to fetch interests based on move-in date and roommate count
        query = """
                SELECT I.username, I.UnitRentID, U.first_name, U.last_name, U.DOB, U.gender, U.email, U.Phone
                FROM Interests AS I
                JOIN Users AS U ON I.username = U.username
                WHERE I.MoveInDate = %s AND I.RoommateCnt = %s
                """
        cursor.execute(query, (move_in_date, roommate_count))
        interests = cursor.fetchall()
            
        # Pass the fetched interests to the HTML template for rendering
        return render_template('search_interest.html', interests=interests)
    
    return render_template('search_interest.html')

def calculate_average_rent(zipcode):
    cursor = conn.cursor()
    
    # SQL query to calculate average monthly rent based on zipcode and number of rooms
    query = """
            SELECT AVG(MonthlyRent) AS average_rent 
            FROM ApartmentUnit AS AU
            JOIN ApartmentBuilding AS AB 
            ON AU.CompanyName = AB.CompanyName AND AU.BuildingName = AB.BuildingName
            WHERE AB.AddrZipCode = %s
            """
    cursor.execute(query, (zipcode,))    
    result = cursor.fetchone()
    
    cursor.close()
    
    return result[0] if result else None

@app.route('/estimate_rent', methods=['GET', 'POST'])
def estimate_rent():
    if request.method == 'POST':
        zipcode = request.form['zipcode']
        # num_rooms = request.form['num_rooms']
        
        # Calculate average monthly rent based on user input
        average_rent = calculate_average_rent(zipcode)
        
        # Pass the calculated average rent to the template for rendering
        return render_template('rent_estimate.html', average_rent=round(average_rent, 2))
    
    return render_template('rent_estimate.html')

@app.route('/add_to_favorites', methods=['POST'])
def add_to_favorites():
    if 'username' in session:
        username = session['username']
        unit_id = request.form['unit_id']
        cursor = conn.cursor()
        # Check if the unit is already in favorites
        cursor.execute('SELECT * FROM Favorites WHERE username = %s AND UnitRentID = %s', (username, unit_id))
        if not cursor.fetchone():
            # Add the unit to favorites
            cursor.execute('INSERT INTO Favorites (username, UnitRentID) VALUES (%s, %s)', (username, unit_id))
            conn.commit()
            flash('Unit added to favorites.')
        else:
            flash('Unit already in favorites.')
        cursor.close()
        return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))

# Route for displaying favorite units
@app.route('/favorites')
def favorites():
    if 'username' in session:
        username = session['username']
        cursor = conn.cursor()
        # Fetch favorite units for the current user
        cursor.execute("""
            SELECT AU.*, AB.*
            FROM ApartmentUnit AU
            JOIN ApartmentBuilding AB ON AU.CompanyName = AB.CompanyName AND AU.BuildingName = AB.BuildingName
            JOIN Favorites F ON AU.UnitRentID = F.UnitRentID
            WHERE F.username = %s
        """, (username,))
        favorite_units = cursor.fetchall()
        cursor.close()
        return render_template('favorites.html', favorite_units=favorite_units)
    else:
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)