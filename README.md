# Automated Test Setup and Usage

## Environment Setup

Run the following commands inside the `test` directory:

```bash
conda create -n zafkiel python=3.9.18
conda activate zafkiel
pip install -r requirements.txt
```

## Before Running Tests

1. Open the Cocos application on the win11 main screen.

2. Run the game in full-screen mode.

3. The supported test resolution is:

   ```text
   2560 × 1600
   ```

4. Verify that the home page matches the reference image:

   ```text
   hearthstone/templates/rawpage.png
   ```
5. login to game and open home page

## Run a Single Task

To run only the dive task:

```bash
python -m hearthstone.login
```

## Run All Tasks

To run the complete automated test suite:

```bash
python main.py
```

[Download the Markdown file](sandbox:/mnt/data/AUTOTEST_README.md)
