from flask import Flask, render_template, request, session, redirect, url_for, flash, escape
import psycopg2
import bcrypt
import hashlib
import os
import math

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
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = escape(request.form['username'])
        password = request.form['password']
        salt = "static_salt"
        salted_password = salt + password
        hashed_password = hashlib.sha256(salted_password.encode()).hexdigest()  # Hash the salted password
        print(hashed_password)
        cursor = conn.cursor()
        query = 'SELECT * FROM Users WHERE username = %s AND passwd = %s'
        cursor.execute(query, (username, hashed_password))
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
        username = escape(request.form['username'])
        password = request.form['password']
        salt = "static_salt"  # Simple static salt
        salted_password = salt + password
        hashed_password = hashlib.sha256(salted_password.encode()).hexdigest()  # Hash the salted password

        first_name = escape(request.form['first_name'])
        last_name = escape(request.form['last_name'])
        dob = request.form['dob']
        gender = escape(request.form['gender'])
        email = escape(request.form['email'])
        phone = escape(request.form['phone'])

        cursor = conn.cursor()
        query = 'INSERT INTO Users (username, passwd, first_name, last_name, DOB, gender, email, Phone) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'
        cursor.execute(query, (username, hashed_password, first_name, last_name, dob, gender, email, phone))
        conn.commit()
        cursor.close()
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/home')
def home():
    if 'username' in session:
        username = escape(session['username'])
        return render_template('home.html', username=username)
    else:
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/search_units', methods=['GET'])
def search_units():
    building_name = escape(request.args.get('building_name'))
    company_name = escape(request.args.get('company_name'))
    pet_name = escape(request.args.get('pet_name'))
    cursor = conn.cursor()
    query = 'SELECT * FROM ApartmentUnit WHERE CompanyName = %s AND BuildingName = %s'
    cursor.execute(query, (company_name, building_name))
    units = cursor.fetchall()
    # Fetch comments for each unit
    unit_comments = {}
    for unit in units:
        unit_comments[unit[0]] = fetch_comments_for_unit(unit[0])
    new_units = []
    for unit in units:
        avg_price_query = '''
            SELECT AVG(MonthlyRent) AS avg_rent 
            FROM ApartmentUnit 
            WHERE SquareFootage BETWEEN 0.9 * %s AND 1.1 * %s 
            AND UnitRentID IN (
                SELECT AU.UnitRentID
                FROM ApartmentUnit AU
                WHERE AU.City = (
                        SELECT AddrCity
                        FROM ApartmentBuilding
                        WHERE CompanyName = %s
                            AND BuildingName = %s
                    );
            );
        '''
        # Convert unit[5] (SquareFootage) to float or decimal if necessary
        avg_price_params = (float(unit[5]), float(unit[5]), unit[1], unit[2])  # Assuming unit[1] is CompanyName, unit[2] is BuildingName
        cursor.execute(avg_price_query, avg_price_params)
        avg_rent = cursor.fetchone()[0]  # Get the average rent
        unit = unit + (math.ceil(avg_rent),)  # Add the average rent to the unit tuple
        new_units.append(unit)
    print(new_units)
    error_message = 'No matching apartment units found. Please check your input and try again.' if not units else None
    cursor.close()
    return render_template('unit_search.html', username=escape(session['username']), units=new_units, unit_comments=unit_comments, error_message=error_message)

@app.route('/add_comment', methods=['POST'])
def add_comment():
    unit_rent_id = request.form['unit_rent_id']
    username = session['username']
    comment_text = request.form['comment_text']
    rating = request.form['rating']
    
    cursor = conn.cursor()
    query = 'INSERT INTO Comments (UnitRentID, username, CommentText, Rating, CommentDate) VALUES (%s, %s, %s, %s, CURRENT_DATE)'
    cursor.execute(query, (unit_rent_id, username, comment_text, rating))
    conn.commit()
    cursor.close()

    return redirect(url_for('search_units'))


def fetch_comments_for_unit(unit_id):
    cursor = conn.cursor()
    query = 'SELECT username, CommentText, Rating FROM Comments WHERE UnitRentID = %s ORDER BY CommentDate DESC'
    cursor.execute(query, (unit_id,))
    comments = [{'username': row[0], 'CommentText': row[1], 'Rating': row[2]} for row in cursor.fetchall()]
    
    cursor.close()
    return comments


@app.route('/search_units_by_pet', methods=['GET'])
def search_units_by_pet():
    pet_name = escape(request.args.get('pet_name'))
    cursor = conn.cursor()
    query = '''
        SELECT AU.UnitRentID, AU.CompanyName, AU.BuildingName, AU.unitNumber, AU.MonthlyRent, AU.squareFootage, AU.AvailableDateForMoveIn,
               PP.isAllowed AS pet_allowed, PP.RegistrationFee, PP.MonthlyFee
        FROM ApartmentUnit AU
        JOIN PetPolicy PP ON AU.CompanyName = PP.CompanyName AND AU.BuildingName = PP.BuildingName
        JOIN Pets P ON P.username = %s AND PP.PetType = P.PetType AND PP.PetSize = P.PetSize
        WHERE P.PetName = %s AND PP.isAllowed = True
    '''
    cursor.execute(query, (session['username'], pet_name))
    units = cursor.fetchall()
    new_units = []
    for unit in units:
        avg_price_query = '''
            SELECT AVG(MonthlyRent) AS avg_rent 
            FROM ApartmentUnit 
            WHERE SquareFootage BETWEEN 0.9 * %s AND 1.1 * %s 
            AND UnitRentID IN (
                SELECT AU.UnitRentID
                FROM ApartmentUnit AU
                WHERE AU.City = (
                        SELECT AddrCity
                        FROM ApartmentBuilding
                        WHERE CompanyName = %s
                            AND BuildingName = %s
                    );
            );
        '''
        # Convert unit[5] (SquareFootage) to float or decimal if necessary
        avg_price_params = (float(unit[5]), float(unit[5]), unit[1], unit[2])  # Assuming unit[1] is CompanyName, unit[2] is BuildingName
        cursor.execute(avg_price_query, avg_price_params)
        avg_rent = cursor.fetchone()[0]  # Get the average rent
        unit = unit + (math.ceil(avg_rent),)  # Add the average rent to the unit tuple
        new_units.append(unit)
    print(new_units)
    cursor.close()
    error_message = 'No matching apartment units found. Please check your input and try again.' if not units else None
    return render_template('unit_search_pet.html', username=escape(session['username']), units=new_units, error_message=error_message)


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

@app.route('/register_pet', methods=['GET', 'POST'])
def register_pet():
    if request.method == 'POST':
        pet_name = escape(request.form['pet_name'])
        pet_type = escape(request.form['pet_type'])
        pet_size = escape(request.form['pet_size'])
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
    query = "SELECT * FROM Pets WHERE username = %s AND petname ILIKE %s"
    cursor.execute(query, (session.get('username'), escape(pet_name)))
    pet_info = cursor.fetchone()
    cursor.close()
    if not pet_info:
        flash('Pet not found or you are not authorized to edit this pet.')
        return redirect(url_for('home'))

    if request.method == 'POST':
        new_pet_name = escape(request.form['pet_name'])
        pet_type = escape(request.form['pet_type'])
        pet_size = escape(request.form['pet_size'])
        cursor = conn.cursor()
        update_query = 'UPDATE Pets SET PetName = %s, PetType = %s, PetSize = %s WHERE username = %s AND petname = %s'
        cursor.execute(update_query, (new_pet_name, pet_type, pet_size, session['username'], pet_name))
        conn.commit()
        cursor.close()
        flash('Pet information updated.')
        return redirect(url_for('home'))

    return render_template('edit_pet.html', pet_info=pet_info)


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


@app.route('/view_interests', methods=['GET', 'POST'])
def view_interests():
    # Initialize interests outside the try-except to ensure it's always defined
    interests = []

    # Fetch all units to populate the form dropdown
    unit_numbers = []
    try:
        cursor = conn.cursor()
        
        # Fetch units always needed for the form dropdown
        # cursor.execute('SELECT DISTINCT unitNumber FROM ApartmentUnit')
        cursor.execute('SELECT unitNumber , CompanyName, BuildingName FROM ApartmentUnit')
        unit_numbers = cursor.fetchall()

        if request.method == 'POST':
            unit_number = request.form['unit_number']  # Get unit number from the form

            # Ensure to fetch interests filtered by the given unit number
            query = '''
                SELECT I.username, U.username, I.RoommateCnt, I.MoveInDate
                FROM Interests I
                JOIN Users U ON I.username = U.username
                JOIN ApartmentUnit AU ON I.UnitRentID = AU.UnitRentID
                WHERE AU.unitNumber = %s
            '''
            cursor.execute(query, (unit_number,))
            interests = cursor.fetchall()  # Only fetch results after executing the query

        cursor.close()  # Close cursor after all operations

    except Exception as e:
        print(f"An error occurred: {e}")
        # Optionally handle error, e.g., by logging or displaying an error message
        flash("An error occurred while fetching data.")

    return render_template('view_interests.html', interests=interests, unit_numbers=unit_numbers)


@app.route('/post_interest', methods=['GET', 'POST'])
def post_interest():
    if 'username' not in session:
        flash('Please login to post interests.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        unit_id = request.form['unit_id']
        roommate_count = request.form['roommate_count']
        move_in_date = request.form['move_in_date']
        cursor = conn.cursor()
        query = 'INSERT INTO Interests (username, UnitRentID, RoommateCnt, MoveInDate) VALUES (%s, %s, %s, %s)'
        cursor.execute(query, (session['username'], unit_id, roommate_count, move_in_date))
        conn.commit()
        cursor.close()
        flash('Interest posted successfully.')
        return redirect(url_for('view_interests'))
    
    # Fetch available units to select from
    cursor = conn.cursor()
    query = 'SELECT UnitRentID, CompanyName, BuildingName, unitNumber FROM ApartmentUnit'
    cursor.execute(query)
    units = cursor.fetchall()
    cursor.close()
    return render_template('post_interest.html', units=units)

@app.route('/advanced_search', methods=['GET', 'POST'])
def advanced_search():
    if request.method == 'POST':
        expected_monthly_rent = request.form['expected_monthly_rent']
        amenities = request.form.getlist('amenities')
        query = 'SELECT * FROM ApartmentUnit WHERE MonthlyRent <= %s'
        params = [expected_monthly_rent]
        if amenities:
            query += ' AND UnitRentID IN (SELECT UnitRentID FROM AmenitiesIn WHERE aType IN %s)'
            params.append(tuple(amenities))
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        units = cursor.fetchall()
        new_units = []
        for unit in units:
            avg_price_query = '''
                SELECT AVG(MonthlyRent) AS avg_rent 
                FROM ApartmentUnit 
                WHERE SquareFootage BETWEEN 0.9 * %s AND 1.1 * %s 
                AND UnitRentID IN (
                    SELECT AU.UnitRentID
                    FROM ApartmentUnit AU
                    WHERE AU.City = (
                            SELECT AddrCity
                            FROM ApartmentBuilding
                            WHERE CompanyName = %s
                                AND BuildingName = %s
                        );
            );
            '''
            # Convert unit[5] (SquareFootage) to float or decimal if necessary
            avg_price_params = (float(unit[5]), float(unit[5]), unit[1], unit[2])  # Assuming unit[1] is CompanyName, unit[2] is BuildingName
            cursor.execute(avg_price_query, avg_price_params)
            avg_rent = cursor.fetchone()[0]  # Get the average rent
            unit = unit + (math.ceil(avg_rent),)  # Add the average rent to the unit tuple
            new_units.append(unit)

        cursor.close()
        if not new_units:
            flash('No matching apartment units found. Please modify your search criteria.')
        return render_template('advanced_search.html', username=escape(session['username']), units=new_units)
    else:
        cursor = conn.cursor()
        query = 'SELECT * FROM Amenities'
        cursor.execute(query)
        amenities = cursor.fetchall()
        cursor.close()
        return render_template('advanced_search.html', amenities=amenities)
    
    
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
