# Simple Python script to rename a whole bunch of files.

This script expects a CSV file as input.  The CSV should contain two columns:

* Column A: the new file name (with or without the .jpg suffix)
* Column B: the original file anem (with the .jpg suffix)

Instructions to run the script are below.

## One time setup:

1. Save this Python script into a text file on your desktop named `rename-pictures.py` (do not use Word, for example -- you must use a text editor, like the TextEdit app).
1. Open the Terminal app.
1. At the Terminal prompt, run this command:
   ```
   chmod +x $HOME/Desktop/rename-pictures.py
   ```
   This simply tells MacOS that the `rename-pictures.py` file is a script that can be executed.
1. Type `exit` to exit the Terminal app.

## Preparation

1. Put all the files you want renamed in a single folder.
2. In the same folder, put a CSV file (not XSLX!) as described above (2 columns, etc.).
3. Make a backup copy of all the files in a different folder somewhere (just in case!)

## Renaming

1. In the Finder, right click on the folder where all your files to be renamed are located.
2. Select "New Terminal at folder".  This will open a new Terminal window.
3. At the Terminal prompt, run this command:
   ```
   $HOME/Desktop/rename.py FILENAME.CSV
   ```
   where you substitute in your CSV's filename (including the `.csv` suffix) for `FILENAME.CSV`.
4. You should see output in the Terminal showing that each of the files were renamed, or errors for files that were not renamed.  You should also see that all the files were renamed in Finder.
