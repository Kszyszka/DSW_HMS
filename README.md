# DSW_HMS

Hotel Management System project for DSW.

---

How to start HMS?

1. Download the code:
   * Option 1: Download code in ZIP from Github
   * Option 2: Clone the repository
     * ```
       git clone https://github.com/Kszyszka/DSW_HMS.git
       ```
2. Make sure that Python 3 (ideally version 3.12.10 is installed)
3. Change the working directory to DSW_HMS
   * ```
     cd DSW_HMS
     ```
4. Install the required dependencies:
   * ```
     python -m pip install -r requirements.txt
     ```
5. Prepare the initial database
   * ```
     python .\manage.py makemigrations
     ```
   * ```
     python .
     ```
6. Prepare a superuser (admin) for your instance
   * ```
     python .\manage.py createsuperuser
     ```
7. Run the application
   * ```
     python .\manage.py runserver
     ```
8. Access the application
   * Open your browser and navigate to:
   * ```
     http://127.0.0.1:8000
     ```

#### Authors:

* Krzysztof Hager 52687
* Krystian Harasymek 54152
* Krystian Galus 52676
* Michał Fuławka 52675
