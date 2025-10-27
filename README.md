# WeatherOpsPlanner
WeatherOpsPlanner is a Python-based logistics and scheduling engine designed for offshore construction and marine operations. It intelligently plans and sequences activities by accounting for weather windows, tidal conditions, and operational downtime, ensuring safer and more efficient project execution.


## Useful Technical Notes
### Source Control with GitHub and VS Code
1. Install VS Code
2. Install the extensions in GitHub called GitHub Pull Requests and GitHub Repositories
3. Make sure git is intallled, use `pip install git` in terminal. (note may be already installed - check with `git --version`)
5. Configure who you are in terminal. `git config --global user.email "YOUR.NAME@email.com"` and `git config --global user.name "YOUR NAME"`
6. Clone repository `git clone https://github.com/YOUR-REPOSITORY-NAME.git` in terminal note this will create folder for repository in terminal directory. You may want to use `cd YOURPATH` to save in an alternative location. *You can copy the HTTPs URL for cloning any repo on GitHub by click green "Code" button*
7. Use the source control `CTRL+SHIFT+G` to push and pull from GitHub.
8. .gitignore: this file stops some files being tracked by GitHub such as virtual environments.

### Virtual environments
1. Create using `py -m venv .venv`.
2. Activate using `.venv\Scripts\activate`.
3. Install packages after activating, you can install what is required from requirements.txt file.
4. Select interpretter in VS Code using `CTRL+SHIFT+P`, click "Python: Choose Interpreter" and choose the .venv you just created.
5. You can install required packages from requirements.txt file using `pip install -r requirements.txt`
6. You can generate a newrequirements.txt file using the command `pip freeze > requirements.txt`
