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

1. Add Sessions to a Conference 

        sudo adduser grader
        
2. Add Sessions to User Wishlist

        sudo nano /etc/sudoers.d/grader
        # Add this line and save the file
        grader ALL=(ALL) NOPASSWD:ALL
        
3. Work on indexes and queries

        cd /home/grader
        mkdir .ssh
        cp /root/.ssh/authorized_keys /home/grader/.ssh/
        chmod 700 .ssh
        chmod 644 .ssh/authorized_keys
        chown -R grader .ssh
        chgrp -R grader .ssh
        
4. Add a Task 

        logout
        ssh -p 22 -i "./ssh/udacity_key.rsa" grader@54.148.43.195
       
        

