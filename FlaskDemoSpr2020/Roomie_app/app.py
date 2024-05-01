from flask import Flask, render_template, request, session, redirect, url_for, flash
import psycopg2
import bcrypt
import hashlib
import os
import math
from functools import wraps
from markupsafe import escape
import logging

app = Flask(__name__)
app.secret_key = 'secret'

db_params = {
    'host': 'database-1.cxeumckggdgy.us-east-2.rds.amazonaws.com',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'pdscsgy1234',
}
conn = psycopg2.connect(**db_params)

def is_user_logged_in():
    return session.get('username')
# Routes

@app.route('/')
def index():
    if is_user_logged_in():
        return redirect(url_for('home'))
    else:
        return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        salt = "static_salt"  # Same salt as used in registration
        salted_password = salt + password
        hashed_password = hashlib.sha256(salted_password.encode()).hexdigest()

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Users WHERE username = %s AND passwd = %s', (username, hashed_password))
        user = cursor.fetchone()
        cursor.close()
        
        if user:
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash('Wrong username or password')
            pass

    return render_template('login.html')



# Utility function to check if user is logged in
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            # flash("Not accessible. Please log in.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


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
        flash('Registration successful!')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/home')
@login_required
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
@login_required
def search_units():
    building_name = escape(request.args.get('building_name'))
    company_name = escape(request.args.get('company_name'))
    pet_allowed = request.args.get('pet_allowed') == 'on'  # Check if pet is allowed
    # pet_name = escape(request.args.get('pet_name'))
    
    cursor = conn.cursor()
    error_message = None
    units = []

    if company_name and building_name:
        query = 'SELECT * FROM ApartmentUnit WHERE CompanyName = %s AND BuildingName = %s'
        cursor.execute(query, (company_name, building_name))
        units = cursor.fetchall()
    if pet_allowed:
        query = '''
            SELECT AU.UnitRentID, AU.CompanyName, AU.BuildingName, AU.unitNumber, AU.MonthlyRent, AU.squareFootage, AU.AvailableDateForMoveIn,
                   PP.isAllowed AS pet_allowed, PP.RegistrationFee, PP.MonthlyFee
            FROM ApartmentUnit AU
            JOIN PetPolicy PP ON AU.CompanyName = PP.CompanyName AND AU.BuildingName = PP.BuildingName
            JOIN Pets P ON P.username = %s AND PP.PetType = P.PetType AND PP.PetSize = P.PetSize
            WHERE PP.isAllowed = True AND PP.CompanyName = %s AND PP.BuildingName = %s
        '''
        cursor.execute(query, (session['username'],company_name, building_name))
        units = cursor.fetchall()
    else:
        error_message = 'Please provide either company name and building name or pet name.'

    if units:
        unit_comments={}
        new_units=[]
        # Fetch comments for each unit
        for unit in units:
            unit_comments[unit[0]] = fetch_comments_for_unit(unit[0])
            avg_price_query = '''
                    SELECT AVG(MonthlyRent) AS avg_rent
                    FROM ApartmentUnit AS AU
                    WHERE SquareFootage BETWEEN 0.9 * %s AND 1.1 * %s 
                    AND UnitRentID IN (
                        SELECT AU.UnitRentID
                        FROM ApartmentUnit AU
                        JOIN ApartmentBuilding AB ON AU.CompanyName = AB.CompanyName AND AU.BuildingName = AB.BuildingName
                        WHERE AB.AddrCity = (
                            SELECT AddrCity
                            FROM ApartmentBuilding
                            WHERE CompanyName = %s
                            AND BuildingName = %s
                        )
                    )
            '''
            # Convert unit[5] (SquareFootage) to float or decimal if necessary
            avg_price_params = (float(unit[5]), float(unit[5]), unit[1], unit[2])  # Assuming unit[1] is CompanyName, unit[2] is BuildingName
            cursor.execute(avg_price_query, avg_price_params)
            avg_rent = cursor.fetchone()[0]  # Get the average rent
            unit = unit + (math.ceil(avg_rent),)  # Add the average rent to the unit tuple
            new_units.append(unit)

        cursor.close()
        if pet_allowed:
            return render_template('unit_search_pet.html', username=escape(session['username']), units=new_units, unit_comments=unit_comments, error_message=error_message)
        else:
            return render_template('unit_search.html', username=escape(session['username']), units=new_units, unit_comments=unit_comments, error_message=error_message)
   
    else:
        cursor.close()
        return render_template('unit_search.html', username=escape(session['username']), error_message=error_message)



@app.route('/add_comment', methods=['POST'])
@login_required
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
@login_required
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
    unit_comments = {}
    for unit in units:
        unit_comments[unit[0]] = fetch_comments_for_unit(unit[0])
        avg_price_query = '''
                SELECT AVG(MonthlyRent) AS avg_rent
                FROM ApartmentUnit AS AU
                WHERE SquareFootage BETWEEN 0.9 * %s AND 1.1 * %s 
                AND UnitRentID IN (
                    SELECT AU.UnitRentID
                    FROM ApartmentUnit AU
                    JOIN ApartmentBuilding AB ON AU.CompanyName = AB.CompanyName AND AU.BuildingName = AB.BuildingName
                    WHERE AB.AddrCity = (
                        SELECT AddrCity
                        FROM ApartmentBuilding
                        WHERE CompanyName = %s
                        AND BuildingName = %s
                    )
                )
        '''
        # Convert unit[5] (SquareFootage) to float or decimal if necessary
        avg_price_params = (float(unit[5]), float(unit[5]), unit[1], unit[2])  # Assuming unit[1] is CompanyName, unit[2] is BuildingName
        cursor.execute(avg_price_query, avg_price_params)
        avg_rent = cursor.fetchone()[0]  # Get the average rent
        unit = unit + (math.ceil(avg_rent),)  # Add the average rent to the unit tuple
        new_units.append(unit)

    cursor.close()
    error_message = 'No matching apartment units found. Please check your input and try again.' if not units else None
    return render_template('unit_search_pet.html', username=escape(session['username']), units=new_units, error_message=error_message, unit_comments=unit_comments)


@app.route('/unit_building_info', methods=['GET'])
@login_required
def unit_building_info():
    error_message = None
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
            # flash('Unit not found')
            error_message="Unit not found"
            return render_template('unit_building_info.html', unit_info=unit_info, error_message=error_message)
    else:
        return redirect(url_for('login'))


@app.route('/register_pet', methods=['GET', 'POST'])
@login_required
def register_pet():
    confirmation_message = ''  # Initialize an empty confirmation message
    if request.method == 'POST':
        pet_name = escape(request.form['pet_name'])
        pet_type = escape(request.form['pet_type'])
        pet_size = escape(request.form['pet_size'])

        # Check if the pet with the same name and type already exists for the user
        cursor = conn.cursor()
        query = 'SELECT COUNT(*) FROM Pets WHERE username = %s AND PetName = %s AND PetType = %s'
        cursor.execute(query, (session['username'], pet_name, pet_type))
        count = cursor.fetchone()[0]
        cursor.close()

        if count > 0:
            confirmation_message = 'A pet with the same name and type already exists.'
        else:
            cursor = conn.cursor()
            insert_query = 'INSERT INTO Pets (username, PetName, PetType, PetSize) VALUES (%s, %s, %s, %s)'
            cursor.execute(insert_query, (session['username'], pet_name, pet_type, pet_size))
            conn.commit()
            cursor.close()
            confirmation_message = 'Pet registration successful.'  # Set the confirmation message
            return redirect(url_for('home'))

    return render_template('register_pet.html', confirmation_message=confirmation_message)

@app.route('/search_and_edit_pets', methods=['GET', 'POST'])
@login_required
def search_and_edit_pets():
    cursor = conn.cursor()
    query = "SELECT * FROM Pets WHERE username = %s"
    cursor.execute(query, (session.get('username'),))
    pets = cursor.fetchall()
    cursor.close()
    
    if request.method == 'POST':
        selected_pet_name = escape(request.form['selected_pet'])
        if not selected_pet_name:
            error_message = 'Please select a pet to edit.'
            return render_template('search_pet.html', pets=pets, error_message=error_message)

        return redirect(url_for('edit_pet', pet_name=selected_pet_name))

    return render_template('search_pet.html', pets=pets)


@app.route('/edit_pet', methods=['POST'])
@login_required
def edit_pet():
    pet_name = escape(request.form['pet_name'])
    pet_type = escape(request.form['pet_type'])
    pet_size = escape(request.form['pet_size'])

    # Check if the updated pet information already exists for the user
    cursor = conn.cursor()
    query = 'SELECT COUNT(*) FROM Pets WHERE username = %s AND PetName = %s AND PetType = %s'
    cursor.execute(query, (session['username'], pet_name, pet_type))
    count = cursor.fetchone()[0]
    query = "SELECT * FROM Pets WHERE username = %s"
    cursor.execute(query, (session.get('username'),))
    pets = cursor.fetchall()
    if count > 0:
        cursor.close()
        error_message = 'A pet with the same name and type already exists.'
        return render_template('search_pet.html', error_message=error_message, pets=pets)

    # Update the pet information
    update_query = 'UPDATE Pets SET PetType = %s, PetSize = %s WHERE username = %s AND petname = %s'
    cursor.execute(update_query, (pet_type, pet_size, session['username'], pet_name))
    conn.commit()
    cursor.close()
    success_message = 'Pet information updated.'
    return render_template('search_pet.html', success_message=success_message, pets=pets)


@app.route('/estimate_rent', methods=['GET', 'POST'])
@login_required
def estimate_rent():
    error_message=None
    if request.method == 'POST':
        zipcode = request.form['zipcode']
        num_rooms = request.form['num_rooms']
        
        # Calculate average monthly rent based on user input
        average_rent = calculate_average_rent(zipcode, num_rooms)
        if average_rent is None:
            error_message="No available units satisfy the given criteria"
            # flash('No available units satisfy the given criteria.')
            return render_template('rent_estimate.html',error_message=error_message)        
        # Pass the calculated average rent to the template for rendering
        return render_template('rent_estimate.html', average_rent=round(average_rent, 2))
    
    return render_template('rent_estimate.html')

        


@app.route('/post_interest', methods=['GET', 'POST'])
@login_required
def post_interest():
    if 'username' not in session:
        # flash('Please login to post interests.')
        return redirect(url_for('login'))

    # Get unit_id from the URL query if available
    selected_unit_id = request.args.get('unit_id', None)

    if request.method == 'POST':
        unit_id = request.form['unit_id']
        roommate_count = request.form['roommate_count']
        move_in_date = request.form['move_in_date']
        cursor = conn.cursor()
        query = 'INSERT INTO Interests (username, UnitRentID, RoommateCnt, MoveInDate) VALUES (%s, %s, %s, %s)'
        cursor.execute(query, (session['username'], unit_id, roommate_count, move_in_date))
        conn.commit()
        cursor.close()
        # flash('Interest posted successfully.')
        return redirect(url_for('search_interest'))
    
    # Fetch available units to select from
    cursor = conn.cursor()
    query = 'SELECT UnitRentID, CompanyName, BuildingName, unitNumber FROM ApartmentUnit'
    cursor.execute(query)
    units = cursor.fetchall()
    cursor.close()
    
    # Render the template with units and potentially a selected unit ID
    return render_template('post_interest.html', units=units, selected_unit_id=selected_unit_id)


@app.route('/advanced_search', methods=['GET', 'POST'])
@login_required
def advanced_search():
    if request.method == 'POST':
        min_rent = request.form['min_rent']
        max_rent = request.form['max_rent']
        amenities = request.form.getlist('amenities')
        query = 'SELECT * FROM ApartmentUnit WHERE MonthlyRent >= %s AND MonthlyRent <= %s'
        params = [min_rent, max_rent]
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
                FROM ApartmentUnit AS AU
                WHERE SquareFootage BETWEEN 0.9 * %s AND 1.1 * %s 
                AND UnitRentID IN (
                    SELECT AU.UnitRentID
                    FROM ApartmentUnit AU
                    JOIN ApartmentBuilding AB ON AU.CompanyName = AB.CompanyName AND AU.BuildingName = AB.BuildingName
                    WHERE AB.AddrCity = (
                        SELECT AddrCity
                        FROM ApartmentBuilding
                        WHERE CompanyName = %s
                        AND BuildingName = %s
                    )
                );
            '''
            # Convert unit[5] (SquareFootage) to float or decimal if necessary
            avg_price_params = (float(unit[5]), float(unit[5]), unit[1], unit[2])  # Assuming unit[1] is CompanyName, unit[2] is BuildingName
            cursor.execute(avg_price_query, avg_price_params)
            avg_rent = cursor.fetchone()[0]  # Get the average rent
            unit = unit + (math.ceil(avg_rent),)  # Add the average rent to the unit tuple
            new_units.append(unit)

        # Storing search criteria in the session to pass to the results page
        session['search_criteria'] = {
            'min_rent': min_rent,
            'max_rent': max_rent,
            'amenities': amenities,
        }

        return redirect(url_for('search_results'))  # Redirect to a new route that will handle the display

    else:
        return render_template('advanced_search.html', amenities=fetch_amenities())

@app.route('/search_results')
@login_required
def search_results():
    # Retrieve search criteria from session
    search_criteria = session.get('search_criteria', {})
    min_rent = search_criteria.get('min_rent', 0)
    max_rent = search_criteria.get('max_rent', 0)
    amenities = search_criteria.get('amenities', [])

    base_query = '''
        SELECT AU.UnitRentID, AU.CompanyName, AU.BuildingName, AU.unitNumber, AU.MonthlyRent, AU.SquareFootage, AU.AvailableDateForMoveIn
        FROM ApartmentUnit AU
        WHERE MonthlyRent >= %s AND MonthlyRent <= %s
    '''
    params = [min_rent, max_rent]
    if amenities:
        base_query += ' AND AU.UnitRentID IN (SELECT UnitRentID FROM AmenitiesIn WHERE aType IN %s)'
        params.append(tuple(amenities))

    cursor = conn.cursor()
    cursor.execute(base_query, tuple(params))
    units = cursor.fetchall()

    new_units = []
    unit_comments = {}
    for unit in units:
        unit_comments[unit[0]] = fetch_comments_for_unit(unit[0])
        avg_price_query = '''
            SELECT AVG(MonthlyRent) AS avg_rent
            FROM ApartmentUnit
            WHERE SquareFootage BETWEEN 0.9 * %s AND 1.1 * %s
            AND UnitRentID IN (
                SELECT AU.UnitRentID
                FROM ApartmentUnit AU
                INNER JOIN ApartmentBuilding AB ON AU.CompanyName = AB.CompanyName AND AU.BuildingName = AB.BuildingName
                WHERE AB.CompanyName = %s
                    AND AB.BuildingName = %s
            );
        '''
        avg_price_params = (float(unit[5]), float(unit[5]), unit[1], unit[2])
        cursor.execute(avg_price_query, avg_price_params)
        avg_result = cursor.fetchone()  # Fetch result once
        avg_rent = avg_result[0] if avg_result else "N/A"  # Check the result here
        unit = unit + (math.ceil(avg_rent) if avg_rent != "N/A" else "N/A",)
        new_units.append(unit)

    cursor.close()
    return render_template('search_results.html', units=new_units, selected_amenities=amenities, min_rent=min_rent, max_rent=max_rent, unit_comments=unit_comments)

def fetch_amenities():
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Amenities')
    amenities = cursor.fetchall()
    cursor.close()
    return amenities


@app.route('/search')
@login_required
def search():
    cursor = conn.cursor()
    query = 'SELECT * FROM Amenities'
    cursor.execute(query)
    amenities = cursor.fetchall()
    cursor.close()
    return render_template('search.html', amenities=amenities)


@app.route('/search_interest', methods=['GET', 'POST'])
@login_required
def search_interest():
    error_message=None
    # Get unit_id from the URL query if available
    selected_unit_number = request.args.get('unit_number', None)

    cursor = conn.cursor()
    cursor.execute('SELECT unitNumber, CompanyName, BuildingName, unitrentid FROM ApartmentUnit')
    unit_numbers = cursor.fetchall()  # Fetch all unit numbers once to use in the dropdown
    interests = []
    unit_number = request.form.get('unit_number')
    print(unit_number)
    if request.method == 'POST':
        move_in_date = request.form.get('move_in_date')
        roommate_count = request.form.get('roommate_count')
        # SQL query to fetch interests based on move-in date and/or roommate count
        if move_in_date or roommate_count or unit_number:  # Filter by move-in date and/or roommate count
            query = '''
                SELECT I.username, I.UnitRentID, U.first_name, U.last_name, I.RoommateCnt, I.MoveInDate, U.gender, U.email, U.Phone, A.unitnumber
                FROM Interests AS I
                JOIN Users AS U ON I.username = U.username
                JOIN ApartmentUnit As A ON A.unitrentid = I.unitrentid
            '''
            params = []
            conditions = []
            if move_in_date:
                conditions.append("I.MoveInDate = %s")
                params.append(move_in_date)
            if roommate_count:
                conditions.append("I.roommatecnt = %s")
                params.append(roommate_count)
            if unit_number != "blank":
                print("hi")
                conditions.append("I.UnitRentId = %s")
                params.append(unit_number)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                cursor.execute(query, tuple(params))
                interests = cursor.fetchall()

        if not interests:
            # flash('No results found. Try different criteria.', 'info')
            error_message="No results found. Try different criteria."
        cursor.close()
        return render_template('search_interest.html', interests=interests, unit_numbers=unit_numbers, selected_unit_number=selected_unit_number,error_message=error_message)
    elif request.method == 'GET':
        params = []
        conditions = []
        query = '''
                SELECT I.username, I.UnitRentID, U.first_name, U.last_name, I.RoommateCnt, I.MoveInDate, U.gender, U.email, U.Phone, A.unitnumber
                FROM Interests AS I
                JOIN Users AS U ON I.username = U.username
                JOIN ApartmentUnit As A ON A.unitrentid = I.unitrentid
            '''
        if selected_unit_number:
            conditions.append("A.UnitNumber = %s")
            params.append(selected_unit_number)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            cursor.execute(query, tuple(params))
            interests = cursor.fetchall()
    return render_template('search_interest.html',unit_number=unit_number, interests=interests, unit_numbers=unit_numbers)






def calculate_average_rent(zipcode, num_rooms):
    cursor = conn.cursor()
    
    # SQL query to calculate average monthly rent based on zipcode and number of rooms
    query = """
            SELECT AVG(MonthlyRent) AS average_rent 
            FROM ApartmentUnit AS AU
            JOIN ApartmentBuilding AS AB 
            ON AU.CompanyName = AB.CompanyName AND AU.BuildingName = AB.BuildingName
            WHERE AB.AddrZipCode = %s AND AU.room = %s
            """
    cursor.execute(query, (zipcode, num_rooms))    
    result = cursor.fetchone()
    
    cursor.close()
    
    return result[0] if result else None


@app.route('/add_to_favorites', methods=['POST'])
@login_required
def add_to_favorites():
    if 'username' not in session:
        # flash('Please log in to add favorites.')
        return redirect(url_for('login'))

    username = session['username']
    unit_id = request.form['unit_id']
    cursor = conn.cursor()
    # Check if the unit is already in favorites
    cursor.execute('SELECT * FROM Favorites WHERE username = %s AND UnitRentID = %s', (username, unit_id))
    if cursor.fetchone():
        # flash('Unit already in favorites.')
        pass
    else:
        # Add the unit to favorites
        cursor.execute('INSERT INTO Favorites (username, UnitRentID) VALUES (%s, %s)', (username, unit_id))
        conn.commit()
        # flash('Unit added to favorites.')
    cursor.close()
    return redirect(url_for('favorites'))


# Route for displaying favorite units
@app.route('/favorites')
@login_required
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
