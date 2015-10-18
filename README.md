# Conference App Project

---

## Introduction

In this project we have to extend the **Conference Central App** developed in the course **Developing Scalable Apps with Python**,
in order to add functionality related to the different *sessions* in a *conceference*

## Requirement

* [Python 2.x](https://www.python.org/downloads/)
* [Google App Engine SDK for Python](https://cloud.google.com/appengine/downloads)

## Installation

* Clone or download **Conference-central** repository on Github
* Follow the instructions of the *README.md* file inside the folder *AppCode*

## Task

These are the steps done in order to configure the server

1. Create a new user named ***grader***

        sudo adduser grader
2. Give the grader the permission to sudo

        sudo nano /etc/sudoers.d/grader
        # Add this line and save the file
        grader ALL=(ALL) NOPASSWD:ALL
3. Copy authorized keys to new user and set privileges

        cd /home/grader
        mkdir .ssh
        cp /root/.ssh/authorized_keys /home/grader/.ssh/
        chmod 700 .ssh
        chmod 644 .ssh/authorized_keys
        chown -R grader .ssh
        chgrp -R grader .ssh
4. Logout and loging as the grader user

        logout
        ssh -p 22 -i "./ssh/udacity_key.rsa" grader@54.148.43.195
5. Update all currently installed packages

        sudo apt-get update
        sudo apt-get upgrade
6. Change the SSH port from 22 to 2200 and dsable the remote root login

        # Set this in /etc/ssh/sshd_config
        sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config_bck
        sudo nano /etc/ssh/sshd_config
        # Modify these line and save the file
        Port 2200
        PermitRootLogin no
        
        # Restart the service
        sudo service ssh restart
        
        # Add the host ip to /etc/hosts in ordet to avoid the message
        # sudo: unable to resolve host ip-10-20-8-135
        sudo nano /etc/hosts
        127.0.1.1 ip-10-20-8-135
        
        # Run the update package again to see if the error persists
        sudo apt-get update
        sudo apt-get upgrade
        
        # Logout acon connect again using the new ssh port
        logout
        ssh -p 2200 -i "./ssh/udacity_key.rsa" grader@54.148.43.195
7. Configure the Uncomplicated Firewall (UFW) to only allow incoming connections 
   for SSH (port 2200), HTTP (port 80), and NTP (port 123)

        sudo ufw status
        sudo ufw default deny incoming
        sudo ufw default allow outgoing
        sudo ufw allow www
        sudo ufw allow ntp
        sudo ufw allow 2200/tcp
        
        # Start the firewall
        sudo ufw enable
        
        # Check the firewall status
        sudo ufw status 
        
        # Logout again to test the firewall
        logout
        ssh -p 2200 -i "./ssh/udacity_key.rsa" grader@54.148.43.195
8. Configure the local timezone to UTC

        date
        # the command dispay the date in utc. Nothing to do
9. Install and configure Apache to serve a Python mod_wsgi application

        sudo apt-get install apache2
        sudo apt-get install libapache2-mod-wsgi
        
        #Set the server name in /etc/apache2/apache2.conf in order to suppress this message
        
        "apache2: Could not reliably determine the server's fully qualified domain name, using 127.0.0.1. 
        Set the 'ServerName' directive globally to suppress this message" 
        
        nano  /etc/apache2/apache2.conf
        ServerName localhost
        .
        # Restart apache
        sudo apache2ctl restart
10. Install PostgreSQL:

        sudo apt-get install postgresql
11. Create a catalog user and databse named catalog

        sudo su - postgres
        psql
        
        # run the following commands
        CREATE USER catalog WITH PASSWORD 'itemcatalogapp';
        CREATE DATABASE catalog;
        GRANT ALL PRIVILEGES ON DATABASE "catalog" to catalog;
        \q
        
        exit
12. Install Git

        sudo apt-get install git
13. Install and configure the ***catalog*** application

        # Clone the app
        cd /var/www
        sudo git clone "https://github.com/rruizriol/item-catalog.git"
        sudo mv item-catalog/AppCode item-catalog/appcode
        sudo mv item-catalog catalog
        
        # Install python package
        sudo apt-get install python-psycopg2
        sudo apt-get install python-flask
        sudo apt-get install python-sqlalchemy
        sudo apt-get install python-pip
        sudo pip install oauth2client
        sudo pip install requests
        sudo pip install httplib2
        sudo pip install dicttoxml
        
        # Modify in the following python files the databse connection to use postgresql
        # engine = create_engine('postgresql://catalog:itemcatalogapp@localhost/catalog')
        cd /var/www/catalog/appcode
        sudo nano database_setup.py
        sudo nano db_helper.py
        sudo nano some_items.py
        
        #Configure the database and add some items
        sudo python /var/www/catalog/appcode/database_setup.py
        sudo python /var/www/catalog/appcode/some_items.py
        
        # Adding the server ip 54.148.43.195 to the to Authorized JavaScript Origins 
        # to the catalog application in Google Developer Console
        # Download the new Json file and add the new content to the  
        # client_secrets.json inside  /var/www/catalog/appcode
        sudo nano /var/www/catalog/appcode/client_secrets.json
        
        # Adding the ip http://54.148.43.195 to the "Valid OAuth redirect URIs" 
        # in the Advanced settins for the catalog application in Facebook
        
        # Create the wsgi file to handle the application
        sudo nano /var/www/catalog/appcode/catalog.wsgi
        
        # Create a catalog user
        sudo adduser catalog
        
        # Add to the site configuration to apache /etc/apache2/sites-available/000-default.conf
        sudo nano /etc/apache2/sites-available/000-default.conf
        
        # Restart the apache
        sudo apache2ctl restart
14. Restrict access to .git folder

        cd /var/www/catalog
        sudo nano .htaccess
        RedirectMatch 404 /\.git        
        

