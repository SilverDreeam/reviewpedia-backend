# Prereq
## Setting up PostgreSQL
1. Download PostgreSQL and have PGAdmin 4 
2. Remember the superuser username and password you have setup
3. Open up PGAdmin 4 and create the database
## Setting up Python Backend
1. After downloading the project, setup your virtual environment in the folder.\
Your libs will be stored in the virtual environment, so you need to use it.

    - Code to setup VE: `py -m venv venv`  

    - Code to run VE for Windows in bash: `source venv/Scripts/activate`
    
2. Make sure you are in VE to install libs.
    
    - Code to install libs: `pip install -r requirements.txt`
    
    - (Optional) Code to reproduce installed requirements.txt `pip freeze > requirements.txt`
    
    - **WARNING**: As of the current state, there is compatibility/deprecation warnings between dj-rest-auth & django-allauth
        - Follow the [guide](https://github.com/iMerica/dj-rest-auth/commit/80feea09c98598c47dc4958a912cb7d510a0561d). I have also included the link in project as reference.
        - The other way is that I have attached the file under folder patchfiles. Simply replace the file in this directory `venv/Lib/site-packages/dj_rest_auth/registration`

3. include the `settings.py` file

4. Now go to settings.py and make the necessary changes.

5. Migration: Also known as loading the database structures into PostgreSQL.
    
    - Its like commit:`python manage.py makemigrations`

    - Its like push: `python manage.py migrate`

6. Create a superuser
    
    - `python manage.py createsuperuser`
    
7. Start the server

    - `python manage.py runserver`

# Normal Startup
1. `cd orbital-backend`
2. `source venv/Scripts/activate`
3. `python manage.py runserver`

# Other Information
## Accessing Database server on web browser
After going to pgAdmin4, under the file section at the top left corner, view logs and capture the link. If you cannot find the link, reload the page.

It will look like: `http://127.0.0.1:5050/?/key=...`

## Creating app
`python manage.py startapp newappname`


## APIs Available
As of now, in development stage, we can use swagger API to help us visualise the APIs. (Sort of a replacement for POSTMAN) Swagger is not accessible while you are logged in, so just incognito.\
The URL(There is a backslash at the end): http://127.0.0.1:8000/swagger/

## Email
With implementation of backend, we will be using this gmail to help us send emails when users want to reset password.

orbital.reviewpedia@gmail.com

## Insertion of data into database
Raw datafiles are all in data folder `cd orbital-backend python manage.py loaddata data/main.json`

### Reset of database
TRUNCATE TABLE public.shops_category RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.shops_region RESTART IDENTITY CASCADE;

# Production-only
## settings.py
Debug=TRUE\
Modify SITE_ID name in admin dashboard\
CORS_ALLOWED_ORIGINS\

## urls.py
swaggers

# Force git
git reset --hard xxx
git push origin HEAD --force
