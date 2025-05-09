import logging
import smtplib
import datetime
import configcreator
import os;
from multiprocessing import Process
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from dotenv import load_dotenv


subject = "Notice of Schedule Change"
text = "The door schedule has been changed"
sender = "yinzstudio@gmail.com"
recipients = configcreator.read_config()['mailinglist'].split(" ")
imagepath = configcreator.read_config()['emailimagepath']

load_dotenv()
password = os.environ.get("GMAIL")


def send_email(subject, body, sender, recipients, password):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)

    text = body
    html = ""
    try:
        with open("email.html") as email:
            html = email.read()
    except FileNotFoundError:
        logging.log("html email not included")
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')
    msg.attach(part1)
    msg.attach(part2)

    
    with open(imagepath, 'rb') as image_file:
        image_data = image_file.read()
        image = MIMEImage(image_data, name=os.path.basename("mercylogo.png"))
        image.add_header('Content-ID', '<image1>')
        msg.attach(image)

    with smtplib.SMTP('smtp.gmail.com', 587) as smtp_server:
       smtp_server.ehlo()
       smtp_server.starttls()
       smtp_server.login(sender, password)
       smtp_server.sendmail(sender, recipients, msg.as_string())
       smtp_server.close()
    print("Message sent!")

def emailfromdoorchange(doorname, originalschedule,newschedule):
    Doorname = doorname
    ogdoorstatus = originalschedule['door_status']
    newdoorstatus = newschedule['door_status']
    starttime = newschedule['start_time'].strftime("%m/%d/%Y, %H:%M:%S")
    endtime = newschedule['end_time'].strftime("%m/%d/%Y, %H:%M:%S")

    msgbody = "The " + Doorname + (" door has changed from being ") + ogdoorstatus + " to " + newdoorstatus + " between the times of " + starttime + " and " + endtime + ". Changes are reflected in the calendar at https://calendar.google.com/calendar/u/0/r" 
    send_email(subject, msgbody, sender, recipients, password)

def emailmultipledoorchange():
    msgbody = "Multiple door schedules in your building have changed. The calendar is available at https://calendar.google.com/calendar/u/0/r."
    send_email(subject,msgbody,sender,recipients,password)
    
originalevent = {'door_status': 'unlocked', 'start_time': datetime.datetime(2025, 3, 20, 17, 30), 'end_time': datetime.datetime(2025, 3, 20, 19, 0)}
newevent = {'door_status': 'access_controlled', 'start_time': datetime.datetime(2025, 3, 21, 16, 30), 'end_time': datetime.datetime(2025, 3, 21, 17, 30)}

#emailfromdoorchange("Atrium",originalevent,newevent)
if __name__ == '__main__':
    p = Process(target=emailfromdoorchange, args=("Atrium",originalevent,newevent))
    p.start()
    p.join()