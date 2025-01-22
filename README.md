# Roomio: Comprehensive Roommate Search Application

## Project Overview
Roomio is a sophisticated roommate search application built with a MySQL backend and Flask frontend. This project integrates advanced search functionalities, user session handling, registration, interest posting, and other essential features across 13 interconnected modules.

---

## Key Features

### 1. User Authentication and Session Management
- Secure login system with password hashing and salting  
- New user registration with comprehensive profile creation  
- Robust session handling for multiple concurrent users  
- Wrong password detection and appropriate error messaging  

### 2. Advanced Apartment Search
- Multi-parameter search functionality (e.g., by building name, location)  
- Pet policy integration in search results  
- Monthly rent and registration fee display based on pet policy  
- Filtering mechanisms for amenities and rent range  
- User-friendly prompts for modifying search criteria when no results are found  

### 3. Pet Registration System
- Ability to register multiple pets with the same name but different types  
- Validation to prevent editing pets with identical name and type  
- Pet policy compliance check for apartment searches  

### 4. Interest Posting and Viewing
- Feature to post and view interests in specific apartment units  
- Real-time updates visible across different user sessions  
- Optional: Interest initiator profile view  

### 5. Detailed Unit and Building Information Display
- Comprehensive information display for selected apartment units  
- Building amenities and policies clearly presented  

### 6. Favorite Units Feature
- Ability to add units to a user's favorites list  
- Persistent favorites across user sessions  
- Easy navigation from favorites to unit information pages  

### 7. Rent Price Analysis
- Average rent price display for search results  
- Optional: Visual representation (e.g., bar charts) of rent prices  

### 8. Database Management
- Implementation of 20+ SQL queries for diverse data scenarios  
- Efficient data retrieval and manipulation for various application features  

### 9. Security Measures
- Protection against SQL injection attacks  
- XSS (Cross-Site Scripting) prevention mechanisms  
- Secure handling of user inputs across the application  

### 10. Responsive Frontend Design
- User-friendly interface built with HTML, CSS, and JavaScript  
- Responsive design for various device sizes  

---

## Technical Highlights
- **Backend:** Flask (Python) with MySQL database  
- **Frontend:** HTML, CSS, JavaScript  
- **Modules:** 13 interconnected modules for comprehensive functionality  
- **Database:** 20+ optimized SQL queries for efficient data management  
- **Security:** Secure user authentication and session handling  
- **Algorithms:** Advanced search and filtering algorithms  
