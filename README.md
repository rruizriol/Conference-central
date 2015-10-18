# Conference App Project

---

## Introduction

In this project we have to extend the **Conference Central App** developed in the course **Developing Scalable Apps with Python**,
in order to add functionality related to the different ***sessions* in a ***conference***

## Requirement

* [Python 2.x](https://www.python.org/downloads/)
* [Google App Engine SDK for Python](https://cloud.google.com/appengine/downloads)

## Installation

* Clone or download **Conference-central** repository on Github
* Follow the instructions of the *README.md* file inside the folder *AppCode*

## Task

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
       
        

