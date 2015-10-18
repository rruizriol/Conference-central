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

These are the definition of the ***Session** class and the ***SessionForm*** class

        class  Session(ndb.Model):
            """Session -- Session object"""
            name            = ndb.StringProperty(required=True)
            highlights      = ndb.StringProperty(repeated=True)
            speaker         = ndb.StringProperty() (required=True)
            duration        = ndb.IntegerProperty()
            typeOfSession   = ndb.StringProperty()
            date            = ndb.DateProperty(required=True)
            startTime       = ndb.TimeProperty(required=True)
        
        class SessionForm(messages.Message):
            """SessionForm -- Session outbound form message"""
            name            = messages.StringField(1)
            highlights      = messages.StringField(2, repeated=True)
            speaker         = messages.StringField(3)
            duration        = messages.IntegerField(4)
            typeOfSession   = messages.StringField(5)
            date            = messages.StringField(6)  # DateTimeField() Y-m-dd
            startTime       = messages.StringField(7)  # TimeField() HH:MM
            websafeKey      = messages.StringField(8)

In the model, the ***session*** belongs to a ***conference***. When a session is created a ***conference*** is specified as the ***session's parent***, this created an ancestor type relation between the ***conference*** and the ***session***. Regarding the desing of the class, most of the attribute are defined as ***string*** type, except the ***date*** field and the ***starTime*** field. The speaker was defined as an attribute of the entity session, and no as an entity. The  denormalization solution was choosen because there no was enough requirements that justify the creation of an entity for the speaker. Also this solution optimizes the process of data reading
        
### Task 2: Add Sessions to User Wishlist

The wish list was impleted as an array property in the ***Profile*** class

        class Profile(ndb.Model):
            """Profile -- User profile object"""
            displayName = ndb.StringProperty()
            mainEmail = ndb.StringProperty()
            teeShirtSize = ndb.StringProperty(default='NOT_SPECIFIED')
            conferenceKeysToAttend = ndb.StringProperty(repeated=True)
            
            # session wish list
            sessionKeysWishlist = ndb.StringProperty(repeated=True)

Also the property was added to the ***ProfileForm*** class

        class ProfileForm(messages.Message):
           """ProfileForm -- Profile outbound form message"""
            displayName = messages.StringField(1)
            mainEmail = messages.StringField(2)
            teeShirtSize = messages.EnumField('TeeShirtSize', 3)
            conferenceKeysToAttend = messages.StringField(4, repeated=True)
            
            # session wish list
            sessionKeysWishlist = messages.StringField(5, repeated=True)
         
### Task 3: Work on indexes and queries

The following two queries were defined:

1. Given a highlight, return all sessions given by this particular highlight, across all conferences. An index for only one field is not required. This is the implemnetation of this query

        sessions = Session.query()
        
        # filter sessions by speaker
        filtered_sessions = sessions.filter(Session.highlights == request.highlight)

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
        
Regarding the following question:

        Solve the following query related problem: Let’s say that you don't
        like workshops and you don't like sessions after 7 pm. How would you handle a query for
        all non-workshop sessions before 7 pm?
        
This implementation

        sessions = Session.query()
        # filter sessions by type and starrtime
        request_time = urllib2.unquote(request.startTime)
        startTime = ConferenceApi._stringToTime(request_time)
        filtered_session = sessions.filter(Session.typeOfSession != request.typeOfSession
                                        , session.startTime <= startTime)

doesn't work due the following restriction of the ***Data Store***

        Only one inequality filter per query is supported. Encountered both duration and startTime
        
The solution is filter by the type and iterate for the result in order to filter by the start time

        sessions = Session.query()
        # filter sessions by type
        filtered_type = sessions.filter(Session.typeOfSession != request.typeOfSession)
        
        # filter by start time
        request_time = urllib2.unquote(request.startTime)
        startTime = ConferenceApi._stringToTime(request_time)
        
        session_forms = SessionForms(items=[])        
        for session in filtered_type:
            if session.startTime <= startTime:
                session_forms.items.append(self._copySessionToForm(session))
        
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
    
