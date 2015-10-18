#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'


from datetime import datetime
import urllib2

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import StringMessage
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import TeeShirtSize

from models import Session
from models import SessionForm
from models import SessionForms

from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE

from utils import getUserId

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
MEMCACHE_FEATURED_SPEAKER_KEY = "FEATURED_SPEAKER"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

FIELDS =    {
            'CITY': 'city',
            'TOPIC': 'topics',
            'MONTH': 'month',
            'MAX_ATTENDEES': 'maxAttendees',
            }

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_BY_CONF_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_BY_TYPE_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    typeOfSession=messages.StringField(2),
)

SESSION_BY_SPEAKER_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    speaker=messages.StringField(1),
)

SESSION_BY_HIGHLIGHT_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    highlight=messages.StringField(1),
)

SESSION_BY_DURATION_START_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    duration=messages.StringField(1),
    startTime=messages.StringField(2),
)

SESSION_BY_TYPE_START_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    typeOfSession=messages.StringField(1),
    startTime=messages.StringField(2),
)

SESSION_POST_WISHLIST_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1)
)

SESSION_POST_CONF_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1)
)

CONF_POST_FEATURED_SPEAKER_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1)
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference', version='v1', audiences=[ANDROID_AUDIENCE],
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID, ANDROID_CLIENT_ID, IOS_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Conference objects - - - - - - - - - - - - - - - - -

    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf


    def _createConferenceObject(self, request):
        """Create or update Conference object, returning ConferenceForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing (both data model & outbound Message)
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]
                setattr(request, df, DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )
        return request


    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)


    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._updateConferenceObject(request)


    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, getattr(prof, 'displayName')) for conf in confs]
        )


    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous filters
                # disallow the filter if inequality was performed on a different field before
                # track the field on which the inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId)) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
                items=[self._copyConferenceToForm(conf, names[conf.organizerUserId]) for conf in \
                conferences]
        )


# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf


    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile      # return Profile


    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        #if field == 'teeShirtSize':
                        #    setattr(prof, field, str(val).upper())
                        #else:
                        #    setattr(prof, field, val)
                        prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)


    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()


    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)


# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement


    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        return StringMessage(data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or "")


# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser() # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[self._copyConferenceToForm(conf, names[conf.organizerUserId])\
         for conf in conferences]
        )


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='filterPlayground',
            http_method='GET', name='filterPlayground')
    def filterPlayground(self, request):
        """Filter Playground"""
        q = Conference.query()
        # field = "city"
        # operator = "="
        # value = "London"
        # f = ndb.query.FilterNode(field, operator, value)
        # q = q.filter(f)
        q = q.filter(Conference.city=="London")
        q = q.filter(Conference.topics=="Medical Innovations")
        q = q.filter(Conference.month==6)

        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, "") for conf in q]
        )
        
# - - - Helpers - - - - - - - - - - - - - - - - - - -
    @staticmethod
    def _getEntityFromWebsafeKey(websafeKey):
        """Gets an Entity from a given websafeKey string"""
        entitykey = ConferenceApi._getKeyFromWebsafeKey(websafeKey)
        return entitykey.get() 
    
    @staticmethod
    def _getKeyFromWebsafeKey(websafeKey):
        """Gets an Entity Key from a given websafeKey string"""
        return ndb.Key(urlsafe=websafeKey)
    
    @staticmethod
    def _stringToDate(value):
        return datetime.strptime(value[:10], '%Y-%m-%d').date()
    
    @staticmethod
    def _stringToTime(value):
        try:
            return datetime.strptime(str(value)[:4], '%H%M').time()
        except:
            return datetime.strptime(str(value)[:5], '%H:%M').time()
    
    @staticmethod
    def _timeToString(time):
        value = str(time)
        return '%s:%s' % (value[:2], value[3:5])
    
    @staticmethod
    def _dateToString(date):
        return str(date)
        
# - - - Session objects - - - - - - - - - - - - - - - - - - -
    def _copySessionToForm(self, session):
        """Copy relevant fields from Session to SessionForm."""
        session_form = SessionForm()
        for field in session_form.all_fields():
            if hasattr(session, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('date'):
                    date = ConferenceApi._dateToString(getattr(session, field.name))
                    setattr(session_form, field.name, date)                             
                elif field.name.endswith('Time'):
                    time = ConferenceApi._timeToString(getattr(session, field.name))
                    setattr(session_form, field.name, time)
                else:
                    setattr(session_form, field.name, getattr(session, field.name))
            elif field.name == "websafeKey":
                setattr(session_form, field.name, session.key.urlsafe())
        session_form.check_initialized()
        return session_form
    
    @endpoints.method(SESSION_BY_CONF_REQUEST, SessionForms,
                      path='getConferenceSessions/{websafeConferenceKey}',
                      http_method='POST', name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """ Given a conference, return all sessions"""
        conf = ConferenceApi._getEntityFromWebsafeKey(request.websafeConferenceKey)
        
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' %
                request.websafeConferenceKey)
            
        # ancestor quey to get all the sessions associated to a conference
        sessions = Session.query(ancestor=conf.key)
        
        # return a Sessionforms
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions])
    
    @endpoints.method(SESSION_BY_TYPE_REQUEST, SessionForms,
                      path='getConferenceSessionsByType/{websafeConferenceKey}'
                      '/{typeOfSession}', http_method='POST',
                      name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Given a conference, return all sessions of a specified type"""
        conf = ConferenceApi._getEntityFromWebsafeKey(request.websafeConferenceKey)
        
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' %
                request.websafeConferenceKey)
            
        # ancestor quey
        sessions = Session.query(ancestor=conf.key)
        
        # filter sessions by type of session
        filtered_sessions = sessions.filter(Session.typeOfSession ==
                                           request.typeOfSession)
        
        # return a Sessionforms
        return SessionForms(
            items=[self._copySessionToForm(session) for session in filtered_sessions])
    
    @endpoints.method(SESSION_BY_SPEAKER_REQUEST, SessionForms,
                      path='getSessionsBySpeaker/{speaker}',
                      http_method='POST', name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """ 
         Given a speaker, return all sessions given by this
         particular speaker, across all conferences
        """
        sessions = Session.query()
        
        # filter sessions by speaker
        filtered_sessions = sessions.filter(Session.speaker == request.speaker)
        
        # return a Sessionforms
        return SessionForms(
            items=[self._copySessionToForm(session) for session in filtered_sessions])
        
    @endpoints.method(SESSION_BY_HIGHLIGHT_REQUEST, SessionForms,
                      path='getSessionsByHighlight/{highlight}',
                      http_method='POST', name='getSessionsByHighlight')
    def getSessionsByHighlight(self, request):
        """ 
        Given a highlight, return all sessions given by this
        particular highlight, across all conferences
        """
        sessions = Session.query()
        
        # filter sessions by speaker
        filtered_sessions = sessions.filter(Session.highlights == request.highlight)
        
        # return a Sessionforms
        return SessionForms(
            items=[self._copySessionToForm(session) for session in filtered_sessions])
        
    @endpoints.method(SESSION_BY_DURATION_START_REQUEST, SessionForms,
                      path='getSessionsByDurationAndLessStartTime/{duration}/{startTime}'
                      , http_method='POST',
                      name='getSessionsByDurationAndLessStartTime')
    def getSessionsByDurationAndLessStartTime(self, request):
        """
        Given a duration and an startTime, return all sessions that have
        a duration equal to the specified duration and the startTime is less than
        the specified startTime
        """
        
        sessions = Session.query()
        
        # filter sessions by duration and start time
        filtered_duration = sessions.filter(Session.duration == int(request.duration))
        
        # filter by start time
        request_time = urllib2.unquote(request.startTime)
        startTime = ConferenceApi._stringToTime(request_time)
        filtered_sessions = filtered_duration.filter(Session.startTime <= startTime)
                
        # return a Sessionforms
        return SessionForms(
            items=[self._copySessionToForm(session) for session in filtered_sessions])
     
    @endpoints.method(SESSION_BY_DURATION_START_REQUEST, SessionForms,
                      path='getSessionsByLessDurationAndStartTime/{duration}/{startTime}'
                      , http_method='POST',
                      name='getSessionsByLessDurationAndStartTime')   
    def getSessionsByLessDurationAndStartTime(self, request):
        """
        Given a duration and an startTime, return all sessions that have
        a duration less than the specified duration and the startTime is less than
        the specified startTime
        """
        
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
        
    @endpoints.method(SESSION_BY_TYPE_START_REQUEST, SessionForms,
                      path='getSessionsByNotTypeAndStartTime/{typeOfSession}/{startTime}'
                      , http_method='POST',
                      name='getSessionsByNotTypeAndStartTime')
    def getSessionsByNoTypeAndStartTime(self, request):
        """
        Given a type and an startTime, return all sessions that are
        a different than the specified type and the startTime is less than
        the specified startTime
        
        This kind of query is not allowed due the following restriction
        "The Datastore rejects queries using inequality filtering on more than one property"
        
        Solution filter by the type and manualy filterted by the start time
        """        
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
        
        # return a Sessionforms       
        return session_forms

        
    @endpoints.method(SESSION_POST_CONF_REQUEST, SessionForm,
            path='session',
            http_method='POST', name='createSession')
    def createSession(self, request):
        """Create new session for a given conference"""
        
        # get the user id
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        
        user_id = getUserId(user)
        
        # get the conference
        conf = ConferenceApi._getEntityFromWebsafeKey(request.websafeConferenceKey)
        
        # do some validations        
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the organizer can create the sessions.')
            
        if not request.name:
            raise endpoints.BadRequestException("The session's name field is required")
        if not request.date:
            raise endpoints.BadRequestException("The session's date field is required")
        if not request.startTime:
            raise endpoints.BadRequestException("The session' startTime field is required")
        
        # create data dictionary
        data = {}
        data['name']          = request.name
        data['highlights']    = request.highlights
        data['speaker']       = request.speaker
        data['duration']      = request.duration
        data['typeOfSession'] = request.typeOfSession
        
        data['date']      = ConferenceApi._stringToDate(request.date)
        data['startTime'] = ConferenceApi._stringToTime(request.date)
  
        # create the key using the conference key as ancestor
        session_id = Session.allocate_ids(size=1, parent=conf.key)[0]
        session_key = ndb.Key(Session, session_id, parent=conf.key)
        data['key'] = session_key

        # write to the datastore
        session = Session(**data)
        session.put()

        # create a task to update featured speaker
        taskqueue.add(
            params={
                'websafeConferenceKey': request.websafeConferenceKey,
                'speaker': request.speaker
            },
            url='/tasks/update_featured_speaker'
        )
        
        # return SessionForm
        return self._copySessionToForm(session) 
        
# - - - Wish List - - - - - - - - - - - - - - - - - - -

    @endpoints.method(message_types.VoidMessage, SessionForms,
                      path='sessions/wishlist',
                      http_method='GET', name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        """Query for all the sessions in a conference that the user is interested in"""
        
        # get the user profile
        profile = self._getProfileFromUser()  # get user Profile
        
        # get all the session keys form the websakekeys stored in the profile
        session_keys = [ConferenceApi._getKeyFromWebsafeKey(websafeKey) for websafeKey in
                     profile.sessionKeysWishlist]
        
        sessions = ndb.get_multi(session_keys)

        # return a Sessionforms
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions])
        
    
    @endpoints.method(SESSION_POST_WISHLIST_REQUEST, SessionForm,
            path='sessions/wishlist',
            http_method='POST', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """Add session to user's list of sessions they are interested to attend"""

        # get the user profile
        profile = self._getProfileFromUser()

        # get session using websafe key
        session = ConferenceApi._getEntityFromWebsafeKey(request.websafeSessionKey)

        # add session websafe key to wishlist
        if not session.key.urlsafe() in profile.sessionKeysWishlist:
            profile.sessionKeysWishlist.append(session.key.urlsafe())
            profile.put()
            
        # return SessionForm
        return self._copySessionToForm(session) 
            
    
    @endpoints.method(SESSION_POST_WISHLIST_REQUEST, SessionForm,
            path='session/{websafeSessionKey}',
            http_method='DELETE', name='removeSessionFromWishlist')
    def removeSessionFromWishlist(self, request):
        """Remove session from user's list of sessions they are interested to attend"""

        # get the user profile
        profile = self._getProfileFromUser()

        # get session using websafe key
        session = ConferenceApi._getEntityFromWebsafeKey(request.websafeSessionKey)

        # add session websafe key to wishlist
        if session.key.urlsafe() in profile.sessionKeysWishlist:
            profile.sessionKeysWishlist.remove(session.key.urlsafe())
            profile.put()
            
        # return SessionForm
        return self._copySessionToForm(session) 
    
# - - - Featured Speaker - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _updateFeaturedSpeaker(websafeConferenceKey, speaker):
        """ Update the featured speaker for the conference"""
        if len(speaker) > 0:
            conf = ConferenceApi._getEntityFromWebsafeKey(websafeConferenceKey)
            
            if not conf:
                raise endpoints.NotFoundException(
                    'No conference found with key: %s' %
                    websafeConferenceKey)
                
            # ancestor quey to get all the sessions associated to a conference
            sessions = Session.query(ancestor=conf.key)
            
            featured = {}
            featured[speaker] = 0
            isFeatured = False
            
            for session in sessions:
                if session.speaker == speaker:
                    featured[speaker] += 1
                    if featured[speaker] > 1:
                        isFeatured = True
                        break
                    
            if isFeatured:
                ConferenceApi._setFeaturedSpeakerInCache(websafeConferenceKey, speaker)
                
                        
    @staticmethod
    def _setFeaturedSpeakerInCache(websafeConferenceKey, speaker):
        """ Set the featured speaker for the conference"""
        cache_key = ConferenceApi._getFeaturedSpeakerCacheKey(websafeConferenceKey)
        memcache.set(cache_key, speaker)        
    
    @staticmethod
    def _getFeaturedSpeakerInCache(websafeConferenceKey):
        """ Set the featured speaker for the conference"""
        cache_key = ConferenceApi._getFeaturedSpeakerCacheKey(websafeConferenceKey)
        return memcache.get(cache_key) or ""
    
    @staticmethod
    def _getFeaturedSpeakerCacheKey(websafeConferenceKey):
        """ Get the featured speaker cache key for a conference"""
        return '%s_%s' % (MEMCACHE_FEATURED_SPEAKER_KEY, websafeConferenceKey)
    
    @endpoints.method(CONF_POST_FEATURED_SPEAKER_REQUEST, StringMessage,
            path='speaker/featured/{websafeConferenceKey}',
            http_method='POST', name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Return the featured speaker of a conference"""
        return StringMessage(data = ConferenceApi._getFeaturedSpeakerInCache(request.websafeConferenceKey))


api = endpoints.api_server([ConferenceApi]) # register API
