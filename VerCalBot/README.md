# Mercy's use of VerCalBot

Mercy uses the [VerCalBot](https://github.com/VerCalBot/VerCalBot) to
syncronize its Verkada door exceptions to an internal/private Google
Calendar.

There is a GitHub action that runs during the work day (e.g., between
6am and 4pm US Eastern time on weekdays) that git clones the VerCalBot
repo and then runs the software from there.

The only things we have in this repo are:

* The Mercy config INI file
* GitHub Action secrets with our Verkada and Google credentials
