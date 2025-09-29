1. python3 manage.py makemigrations
2. python3 manage.py migrate
3. python3 manage.py runserver 

1. `cd orbital-backend`
2. `.\venv\Scripts\activate` OR `source ./venv/bin/activate` OR `source venv/Scripts/activate`
3. `python3 manage.py loaddata data/1.json`
4. `python3 manage.py loaddata data/2.json`
5. `python3 manage.py loaddata data/reviewdata.json`

1. python manage.py createsuperuser

TRUNCATE TABLE public.shops_review RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.shops_category RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.shops_region RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.users_user RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.users_vendor RESTART IDENTITY CASCADE;
TRUNCATE TABLE public.users_reviewer RESTART IDENTITY CASCADE;