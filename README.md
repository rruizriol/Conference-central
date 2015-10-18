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

## Tasks

### Task 1: Add Sessions to a Conference 

        sudo adduser grader
        
### Task 2: Add Sessions to User Wishlist
   
   The tash

        sudo nano /etc/sudoers.d/grader
        # Add this line and save the file
        grader ALL=(ALL) NOPASSWD:ALL
        
### Task 3: Work on indexes and queries

The following two queries were defined:

1. 

2. Given a duration and an startTime, return all sessions that have a duration less than the specified duration and the
startTime is less than the specified startTime, across all conferences. For this query the following index was added to the file ***index.yaml***. 

        - kind: Session
          properties:
          - name: duration
          - name: startTime
          
This is the implementation of the query

        sessions = Session.query()
        
        # filter sessions by duration and start time
        filtered_duration = sessions.filter(Session.duration <= int(request.duration))
        
        # filter by start time
        request_time = urllib2.unquote(request.startTime)
        startTime = ConferenceApi._stringToTime(request_time)
        
        session_forms = SessionForms(items=[])        
        for session in filtered_duration:
            if session.startTime <= startTime:
                session_forms.items.append(self._copySessionToForm(session))
        
        # return a Sessionforms       
        return session_forms
        
### Task 4: Add a Task 

After created a session a task was generated in order to set the featured speaker for a conference. The task was implemented using the ***taskqueue** class of the ***google app engine***. 

        taskqueue.add(
            params={
                'websafeConferenceKey': request.websafeConferenceKey,
                'speaker': request.speaker
            },
            url='/tasks/update_featured_speaker'
        )

The task received as a parameter the the ***session's speaker*** and the ***conference's websafe key***. When the task is executed, it check if the speaker mets the condictions of a featured speaker (the speaker is the speaker in more thana one conference). If the spaeker is a featured speaker the speaker's value is persisted in the ***memcache***. The key for the vaiue in the ***memcache*** is built using a default key and the ***conference's websafe key***  

These are the helper methods created in order to work with the ***memcache***

        @staticmethod
        def _setFeaturedSpeakerInCache(websafeConferenceKey, speaker):
                """ Set the featured speaker for the conference from memcache"""
                cache_key = ConferenceApi._getFeaturedSpeakerCacheKey(websafeConferenceKey)
                memcache.set(cache_key, speaker)
                
        @staticmethod        
        def _getFeaturedSpeakerInCache(websafeConferenceKey):
                """ Set the featured speaker for the conference in memcache"""
                cache_key = ConferenceApi._getFeaturedSpeakerCacheKey(websafeConferenceKey)
                return memcache.get(cache_key) or ""
                
        @staticmethod       
        def _getFeaturedSpeakerCacheKey(websafeConferenceKey):
                """ Get the featured speaker cache key for a conference"""
                return '%s_%s' % (MEMCACHE_FEATURED_SPEAKER_KEY, websafeConferenceKey)
    
    
    
        

        
       
        

