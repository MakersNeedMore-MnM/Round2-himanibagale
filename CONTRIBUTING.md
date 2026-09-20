# Contributing to CodeLith

Small fixes, documentation updates, tests, and new ideas are all welcome.

## Get the code

1. Fork the repository on GitHub.
2. Clone your fork and enter the project:

```powershell
git clone https://github.com/<your-username>/Round2-himanibagale.git
cd Round2-himanibagale
```

3. Create a branch for your change:

```powershell
git checkout -b improve-short-description
```

4. Create a virtual environment and install the project:

```powershell
py -m venv .venv
.venv\Scripts\activate
py -m pip install -e .
```

## Make and check your change

Keep changes focused and follow the existing code style. Add or update tests when
behavior changes, then run:

```powershell
python -m pytest tests/ -v
```

For dashboard changes, run the frontend checks from `frontend/` as appropriate:

```powershell
npm install
npm run build
```

## Submit your contribution

Commit your work with a clear message, push your branch, and open a pull request
from your fork to the main repository. Describe what changed, why it helps, and
how you tested it. Include screenshots for visible dashboard changes.

Please keep pull requests focused so they are easy to review. 
