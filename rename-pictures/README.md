# Simple Python script to rename a whole bunch of files.

This script expects a CSV file as input.  The CSV should contain two columns:

* Column A: the new file name (with or without the .jpg suffix)
* Column B: the original file anem (with the .jpg suffix)

Instructions to run the script are below.

## One time setup:

1. Save this Python script into a text file on your desktop named
   `rename-pictures.py` (do not use Word, for example -- you must use
   a text editor, like the TextEdit app.  Or you can download the text
   file from
   https://raw.githubusercontent.com/MercyAcademy/mercy/master/rename-pictures/rename-pictures.py).
   * The easiest method is to select File-->Save As in your web
     browser to save the file as `rename-pictures.py` on your Desktop.
1. Open the Terminal app.
1. At the Terminal prompt, run this command:
   ```
   chmod +x $HOME/Desktop/rename-pictures.py
   ```
   This simply tells MacOS that the `rename-pictures.py` file is a script that can be executed.
1. Type `exit` to exit the Terminal app.
1. It will say that the process has ended, and you can close the
   Terminal window.

## Preparation

1. Put all the files you want renamed in a single folder.
2. In the same folder, put a CSV file (not XSLX!) as described above (2 columns, etc.).
3. Make a backup copy of all the files in a different folder somewhere (just in case!)

## Renaming

1. In the Finder, right click on the folder where all your files to be renamed are located.
1. Select "New Terminal at folder".  This will open a new Terminal
   window.
1. At the Terminal prompt, run this command:
   ```
   $HOME/Desktop/rename-pictures.py FILENAME.CSV
   ```
   where you substitute in your CSV's filename (including the `.csv`
   suffix) for `FILENAME.CSV`.
   * **NOTE:** It is simpler if your `FILENAME.CSV` does not contain
     any spaces.
   * You *can* include spaces in the filename if you want to, but you
     will need to add `\` before each space on the command line.
1. The first time you run this, MacOS will popup a dialog box saying
   that you need to install the developer command line tools.  Go
   ahead and install them.
   * You'll also see an error message about how `rename-pictures.py`
     failed.  **This is ok.**
   * Once MacOS finishes installing the developer tools, run the
     command again.
1. You should see output in the Terminal showing that each of the
   files were renamed, or errors for files that were not renamed.  You
   should also see that all the files were renamed in Finder.
