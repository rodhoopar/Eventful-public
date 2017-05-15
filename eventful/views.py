from __future__ import absolute_import
from django.shortcuts import render
from django.views.generic.edit import CreateView
from django.contrib.auth.forms import UserCreationForm
from .forms import EventCreationForm, VolunteerCreationForm, TaskCreationForm, CSVForm
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, login, logout
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Event, Volunteer, Task
from django.forms.formsets import formset_factory
from functools import partial, wraps
from django_twilio.request import decompose
from django.views.decorators.csrf import csrf_exempt
from twilio.rest import Client
from django.conf import settings
from django.core import serializers
from .tasks import send_sms_reminder, reassign
from django.utils import timezone
import re
import pusher
import json
import unicodecsv as csv

# Twilio Client
account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
auth_token = getattr(settings, "TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)

# Pusher Client
pusher_client = pusher.Pusher(
  app_id='334669',
  key='acdc038504e0938fda16',
  secret='e6c88416d0522bf98d2e',
  ssl=True
)

# Home page
def index(request): 
	next_page = request.GET.get('next', '/create')
	if request.user.is_authenticated():
		return HttpResponseRedirect(next_page)
	error = ""
	
	# Try to log in the user
	if request.method == 'POST':
		form = AuthenticationForm(request.POST)
		username = request.POST['username']
		password = request.POST['password']
		user = authenticate(username=username, password=password)
		if user is not None: 
			login(request, user)
			return HttpResponseRedirect(next_page)
		else: 
			error = "Incorrect username/password"
	
	else:
		form = AuthenticationForm()
	return render(request, 'eventful/index.html', {'form': form, 'error': error}) 

# Registration page (class based view)
class register(CreateView): 
	template_name = 'eventful/register.html'
	form_class = UserCreationForm
	success_url = '/'

# Event creation page
@login_required()
def create(request): 
	# Redirect if event exists
	try: 
		event = Event.objects.get(organizer=request.user)
		return HttpResponseRedirect('/manage')
	
	# Render/handle creation page
	except Event.DoesNotExist: 
		if request.method == 'POST':
			form = EventCreationForm(request.POST, request=request)
			if form.is_valid(): 
				form.save()
				return HttpResponseRedirect('/add')
		else:
			form = EventCreationForm()
		messages.success(request, "Please create a new event, as an old one may have ended or expired.")
		return render(request, 'eventful/create.html', {'form': form})
class Create(CreateView): 
	template_name = 'eventful/create.html'
	form_class = EventCreationForm
	success_url = '/add'

# Volunteer addition page
@login_required()
def add(request): 
	try: 
		event = Event.objects.get(organizer=request.user)
		form = VolunteerCreationForm()
		csvform = CSVForm()
		
		# Capture form or CSV upload
		if request.method == 'POST':
			if request.FILES:
				csvform = CSVForm(request.POST, request.FILES, request = request)
				if csvform.is_valid():
					csvform.save()
			else:
				form = VolunteerCreationForm(request.POST, request=request)
				if form.is_valid(): 
					form.save()
					messages.success(request, "Successfully added 1 volunteer.")
		
		else: 
			form = VolunteerCreationForm()
		return render(request, 'eventful/add.html', {'form': form, 'csvform': csvform, 'event': event})
	
	# Event must be created first
	except Event.DoesNotExist: 
		return HttpResponseRedirect('/create')

# Event settings page
@login_required()
def event_settings(request): 
	try:
		event = Event.objects.get(organizer=request.user)
		
		# Capture entered settings
		if request.method == 'POST':
			newHighP = request.POST.get('highP')
			newLowP = request.POST.get('lowP')
			
			# Make sure integer is entered
			try: 
				newHighP = int(newHighP)
				newLowP = int(newLowP)
			except: 
				messages.success(request, 'Timeouts must be integers between 30 and 32767 seconds')
				return render(request, 'eventful/settings.html', {'event': event})
			
			# Make sure in right range
			r = range(30, 32767)
			if not newHighP in r or not newLowP in r: 
				messages.success(request, 'Timeouts must be integers between 30 and 32767 seconds')
				return render(request, 'eventful/settings.html', {'event': event})
			
			# Save settings
			event.highPriority = newHighP
			event.lowPriority = newLowP
			event.save()
			messages.success(request, 'Event Settings Updated.')
		
		return render(request, 'eventful/settings.html', {'event': event})
	
	except Event.DoesNotExist: 
		return HttpResponseRedirect('/create')

# Event dashboard page
@login_required()
def manage(request): 
	try: 
		# Get relevant context from DB
		event = Event.objects.get(organizer=request.user)
		all_volunteers = Volunteer.objects.filter(organizer=request.user)
		incomplete_tasks = Task.objects.filter(organizer=request.user).exclude(status='Completed')
		completed_tasks = Task.objects.filter(organizer=request.user, status='Completed')
		volunteers = Volunteer.objects.filter(organizer=request.user, status='Free')
		form = TaskCreationForm(initial={'volunteer': 'Random'})
		form.fields['volunteer'].queryset = volunteers
		form.fields['volunteer'].required = False
		categories = Volunteer.objects.filter(organizer=request.user).order_by('category').values_list('category', flat=True).distinct()
		categories = list(set([x.lower() for x in categories]))
		
		# Capture POST data
		if request.method == 'POST':
			# Handle task assignment
			if 'assign' in request.POST: 
				form = TaskCreationForm(request.POST, request=request)
				form.fields['volunteer'].queryset = volunteers
				previous_id = request.POST.get('previous_id')
				if previous_id: 
					Task.objects.get(id=previous_id).delete()
				if form.is_valid(): 
					form.save()
        			return HttpResponseRedirect('/manage')
	        
        	# Handle deletion of incomplete task
	        if 'deletetask' in request.POST: 
	        	task_id = request.POST.get('task_id')
	        	task = Task.objects.get(organizer=request.user, id=task_id)
	        	volunteer = Volunteer.objects.get(pk=task.volunteer_id)
	        	
	        	# Notify volunteer of deletion
	        	if not volunteer.status.lower() == "unavailable":
		        	to = volunteer.phone
	        		from_ = settings.TWILIO_NUMBER
	        		body = 'The task "' + task.description + '" has been CANCELLED.'
	        		if not volunteer.unsubscribed:
	        			client.messages.create(to=to, from_=from_, body=body)
	        			messages.warning(request, "Task Deleted")
	        		else: 
	        			messages.warning(request, "Task Deleted. This volunteer's phone number is unsubscribed from Eventful. Please contact them directly to resolve the issue.")
		        	volunteer.status = 'Free'
		        	volunteer.save()
	        	
	        	task.delete()
	        	return HttpResponseRedirect('/manage')
	        
	        # Handle deletion of completed task
	        if 'deletetask_completed' in request.POST:
	        	task_id = request.POST.get('task_id')
	        	task = Task.objects.get(organizer=request.user, id=task_id)
	        	task.delete()
	        	messages.warning(request, "Task Deleted")
	        	return HttpResponseRedirect('/manage')
	       	
	        # Handle deletion of volunteer
	       	if 'deletevolunteer' in request.POST: 
	       		volunteer_id = request.POST.get('volunteer_id')
	       		volunteer = Volunteer.objects.get(pk=volunteer_id)
	       		
	       		# Notify volunteer of their removal
	       		to = volunteer.phone
	       		from_ = settings.TWILIO_NUMBER
	       		body = "You've been removed as a volunteer from the event " + event.name + ". Please contact your organizer directly if you think there's been a mistake."
	       		if not volunteer.unsubscribed:
	       			client.messages.create(to=to, from_=from_, body=body)
	       		
	       		volunteer.delete()
	       		messages.warning(request, "Volunteer Deleted")
	       		return HttpResponseRedirect('/manage')
	       	
	       	if 'updatename' in request.POST:
	       		volunteer_id = request.POST.get('volunteer_id')
	       		new_name = request.POST.get('new_name')

	       		# Verify name not already being used
	       		if Volunteer.objects.filter(organizer=request.user, name=new_name):
	       			messages.warning(request, 'This name is already in use in this event.')
	       			return HttpResponseRedirect('/manage')

	       		volunteer = Volunteer.objects.get(pk=volunteer_id)
	       		volunteer.name = new_name
	       		volunteer.save()
	       		messages.info(request, "Volunteer Name Updated")
	       		return HttpResponseRedirect('/manage')

	       	# Handle updating of volunteer category
	       	if 'updatecategory' in request.POST:
	       		volunteer_id = request.POST.get('volunteer_id')
	       		new_category = request.POST.get('new_category')
	       		volunteer = Volunteer.objects.get(pk=volunteer_id)
	       		volunteer.category = new_category
	       		volunteer.save()
	       		
	       		# Update categories list
	       		categories = Volunteer.objects.order_by('category').values_list('category', flat=True).distinct()
	       		categories = list(set([x.lower() for x in categories]))
	       		messages.info(request, "Volunteer Category Updated")
	       		return HttpResponseRedirect('/manage')
	       	
	       	# Handle updating of volunteer phone number
	       	if 'updatephone' in request.POST:
	       		volunteer_id = request.POST.get('volunteer_id')
	       		new_phone = request.POST.get('new_phone')
	       		new_phone = re.sub('\+1', '', new_phone)
	       		new_phone = re.sub('[-\ ()]', '', new_phone)

	       		# Validate the new number
	       		if len(new_phone) != 10 or not new_phone.isdigit():
	       			messages.warning(request, "Error: Phone Number Invalid")
	       		else:
	       			volunteer = Volunteer.objects.get(pk=volunteer_id)
	       			if new_phone == volunteer.phone: return HttpResponseRedirect('/manage')
	       			if Volunteer.objects.filter(phone=new_phone): 
	       				messages.warning(request, 'This phone number is already in use.')
	       				return HttpResponseRedirect('/manage')
	       			old_phone = volunteer.phone
	       			
	       			# Notify new number
	       			to = new_phone
	       			from_ = settings.TWILIO_NUMBER
	       			body = 'You\'ve been added as a volunteer to the event "' + event.name + '"\nIf at any time you\'re unavailable during this event, reply "unavailable" to let your organizer know.'
	       			try: 
	       				client.messages.create(to=to, from_=from_, body=body)
	       				messages.info(request, "Volunteer Phone Number Updated")
	       				volunteer.phone = new_phone
	       				
	       				# Notify old number of removal
	       				to = old_phone
	       				body = "You have been disconnected from the event " + event.name + ". Please contact your organizer directly if you think there's been a mistake."
	       				if not volunteer.unsubscribed:
	       					client.messages.create(to=to, from_=from_, body=body)
	       				volunteer.unsubscribed = False
	       				volunteer.save()
	       			except: 
	       				messages.warning(request, "Error: New phone number does not exist, is not active, or is unreachable from Eventful. Could not update.")
	       		return HttpResponseRedirect('/manage')
	       	
	       	# Handle an announcement 
	       	if 'announce' in request.POST:
	       		message = request.POST.get('message')
	       		category = request.POST.get('category')
	       		
	       		# Filter by category if one was selected
	       		if category: 
	       			volunteers_announce = Volunteer.objects.filter(organizer=request.user, category__iexact=category)
	       		else: 
	       			volunteers_announce = Volunteer.objects.filter(organizer=request.user)
	       		
	       		# Announce to all volunteers
	       		from_ = settings.TWILIO_NUMBER
        		body = 'Announcement from your organizer: "' + message + '".'
        		num_unreachable = 0
        		made = False
	       		for volunteer in volunteers_announce: 
	       			made = True
	       			if not volunteer.unsubscribed:
	       				to = volunteer.phone
	       				client.messages.create(to=to, from_=from_, body=body)
	       			else:
	       				num_unreachable+=1
	       		
	       		if made: 
		       		if num_unreachable:
		       			messages.success(request, "Announcement Made. Some volunteer's phone numbers were unreachable.")
		       		else: 
		       			messages.success(request, "Announcement Made")
	       		return HttpResponseRedirect('/manage')
	       	
	       	# Handle a direct message
	       	if 'directmessage' in request.POST: 
	       		to = request.POST.get('volunteer_phone')
	       		from_ = settings.TWILIO_NUMBER
	       		body = 'Direct Message from your organizer: "' + request.POST.get('message') + '".'
	       		volunteer = Volunteer.objects.get(phone=to)
	       		
	       		if not volunteer.unsubscribed:
	       			client.messages.create(to=to, from_=from_, body=body)
	       			messages.success(request, "Message Sent")
	       		else:
	       			messages.warning(request, "This volunteer's phone number is unsubscribed from Eventful. Please contact them directly to resolve the issue.")
	       		
	       		return HttpResponseRedirect('/manage')
	       	
	       	# Handle event ending, redirect to end page
	       	if 'end' in request.POST:
	       		volunteers_end = Volunteer.objects.filter(organizer=request.user)
	       		from_ = settings.TWILIO_NUMBER
	       		body = 'Your organizer has ended the event ' + event.name + '. Thank you for volunteering!'
	       		
	       		# Notify each volunteer of end
	       		for volunteer in volunteers_end: 
	       			to = volunteer.phone
	       			if not volunteer.unsubscribed:
	       				client.messages.create(to=to, from_=from_, body=body)
	       		return HttpResponseRedirect('/end')
	       	
	       	# Handle updating of task description
	       	if 'updatedescription' in request.POST: 
	       		task_id = request.POST.get('task_id')
	       		new_description = request.POST.get('new_description')
	        	task = Task.objects.get(organizer=request.user, id=task_id)
	        	volunteer = Volunteer.objects.get(pk=task.volunteer_id)
	        	
	        	# Different text based on volunteer status
	        	if volunteer.status.lower() == "pending":
	        		body = 'The task has been updated with new instructions: "' + new_description + '"\nReply "yes" if you can do the task!'
	        	elif volunteer.status.lower() == "working": 
	        		body = 'The task has been updated with new instructions: "' + new_description + '"\nWhen finished with the task, please reply saying "done".'
	        	to = volunteer.phone
	        	from_ = settings.TWILIO_NUMBER
	        	
	        	if not volunteer.unsubscribed:
	        		client.messages.create(to=to, from_=from_, body=body)
	        		messages.info(request, "Task Description Updated")
	        	else:
	        		messages.warning(request, "Task Description Updated. This volunteer's phone number is unsubscribed from Eventful. Please contact them directly to resolve the issue.")
	        	
	        	task.description = new_description
	        	task.save()
	        	return HttpResponseRedirect('/manage')
		return render(request, 'eventful/manage.html', {'form': form, 
			'all_volunteers': all_volunteers, 
			'incomplete_tasks': incomplete_tasks,
			'completed_tasks': completed_tasks,
			'event': event,
			'free_volunteers': volunteers,
			'categories': categories}) 
	except Event.DoesNotExist: 
		return HttpResponseRedirect('/create')
	except Volunteer.DoesNotExist: 
		return HttpResponseRedirect('/manage')
	except Task.DoesNotExist:
		return HttpResponseRedirect('/manage')

# Log out the user
@login_required()
def logout_view(request):
	logout(request)
	return HttpResponseRedirect('/')

# Event end page
@login_required()
def end(request): 
	try: 
		event = Event.objects.get(organizer=request.user)
		event.total_responsetime = 0
		volunteers_queryset = Volunteer.objects.filter(organizer=request.user)
		volunteers = []
		
		# Calculate summary statistics
		for volunteer in volunteers_queryset: 
			if volunteer.num_assigned == 0: 
				volunteer.percent_accepted = 0
			else: 
				volunteer.percent_accepted = int(100 * float(volunteer.num_accepted)/float(volunteer.num_assigned))
			volunteers.append(volunteer)
			event.total_responsetime += volunteer.avg_responsetime
		
		if event.total_assigned == 0: 
			event.percent_accepted = 0
			event.percent_reassigned = 0
		else: 
			event.percent_accepted = int(100 * float(event.total_accepted)/float(event.total_assigned))
			event.percent_reassigned = int(100 * float(event.total_reassigned)/float(event.total_assigned))
		
		divisor = len([x for x in volunteers if x.avg_responsetime != 0])
		if divisor == 0: 
			event.avg_responsetime = 0
		else: 
			event.avg_responsetime = event.total_responsetime/divisor
		
		# Delete from DB
		Event.objects.filter(organizer=request.user).delete()
		Volunteer.objects.filter(organizer=request.user).delete()
		Task.objects.filter(organizer=request.user).delete()
		
		return render(request, 'eventful/end.html', {'event': event, 'volunteers': volunteers})
	except Event.DoesNotExist:
		return HttpResponseRedirect('/create')

# Volunteer csv download
@login_required()
def volunteers(request): 
	try: 
		event = Event.objects.get(organizer=request.user)
		volunteers = Volunteer.objects.filter(organizer=request.user)
		response = HttpResponse(content_type='text/csv')
		response['Content-Disposition'] = 'attachment; filename="' + event.name + '_volunteers.csv"'
		writer = csv.writer(response)
		
		# Write each volunteer to file and return it
		for volunteer in volunteers:
			if volunteer.category: 
				writer.writerow([volunteer.name, volunteer.phone, volunteer.category])
			else: 
				writer.writerow([volunteer.name, volunteer.phone])
		return response
	
	except Event.DoesNotExist: 
		return HttpResponseRedirect('/create')

# Handle texts from Twilio
@csrf_exempt
def sms(request): 
	try:
		twilio_request = decompose(request)
		text = twilio_request.body.strip().lower()
		volun = twilio_request.from_
		person = Volunteer.objects.get(phone=volun[2:])
		event = Event.objects.get(organizer=person.organizer)
		
		# Handle unsubscribing texts
		if text == 'unsubscribe' or text == 'stop':
			person.unsubscribed = True
			person.save()
			pusher_client.trigger('gone', 'my-event', {'event': event.id, 'name': person.name})
		
		# Handle resubscribing texts
		elif text == 'start' or text == 'subscribe':
			if person.unsubscribed == True:
				person.unsubscribed = False
				person.save()

				# Return response based on status before unsubscribing
				if person.status.lower() == "pending":
					twiml = '<Response><Message> Please text back "yes" or "no" to let the organizer know whether you can do your assigned task.</Message></Response>'
					return HttpResponse(twiml, content_type='text/xml')
				elif person.status.lower() == "working":
					twiml = '<Response><Message> Please text "done" when you have finished your task.</Message></Response>'
					return HttpResponse(twiml, content_type='text/xml')
				elif person.status.lower() == "unavailable":
					twiml = '<Response><Message> Please text back "available" as soon as you are available to work again.</Message></Response>'
					return HttpResponse(twiml, content_type='text/xml')
			else:
				twiml = '<Response><Message>Didn\'t quite get that. Please text again.</Message></Response>'
				return HttpResponse(twiml, content_type='text/xml')
		
		# Handle "yes" texts
		elif 'yes' == text:
			# Person accepts task 
			if person.status.lower() == "pending":
				if person.unsubscribed:
					person.unsubscribed = False
					person.save()
					twiml = '<Response><Message> Please let the organizer know if you can do your assigned task by replying "yes".</Message></Response>'
				else:
					person.status = 'Working'
					if event.total_accepted < settings.PSIF_MAX:
						event.total_accepted += 1
						event.save()
					total = person.avg_responsetime*person.num_accepted
					if person.num_accepted < settings.PSIF_MAX: 
						person.num_accepted += 1 
					new_avg_responsetime = int(((timezone.now() - person.latest_assignment).total_seconds() + total)/person.num_accepted)
					if new_avg_responsetime < settings.PSIF_MAX: 
						person.avg_responsetime = new_avg_responsetime
					else: 
						person.avg_responsetime = PSIF_MAX
					person.save(update_fields=['status', 'num_accepted', 'avg_responsetime'])
					task = Task.objects.get(volunteer_id=person.id, status="Pending")
					task.status = 'In Progress'
					task.save(update_fields=['status'])
					twiml = '<Response><Message>Thanks for accepting the task: "' + task.description + '"\nWhen finished with the task, please reply saying \"done\".</Message></Response>'
					pusher_client.trigger('yes', 'my-event', {'event': event.id, 'phone': person.phone, 'time': person.avg_responsetime,'assign': person.num_assigned,'id': person.id, 'name': person.name, 'status': person.status, 'task': task.id, 'taskstat': task.status, 'taskname': task.description, 'accept': person.num_accepted})
				return HttpResponse(twiml, content_type='text/xml')
			# Person is resubscribing
			elif person.unsubscribed:
				person.unsubscribed = False
				person.save()
				if person.status.lower() == "working":
					twiml = '<Response><Message> Please text "done" when you have finished your task.</Message></Response>'
					return HttpResponse(twiml, content_type='text/xml')
				elif person.status.lower() == "unavailable":
					twiml = '<Response><Message> Please text back "available" as soon as you are available to work again.</Message></Response>'
					return HttpResponse(twiml, content_type='text/xml')
			
			else: 
				twiml = '<Response><Message>Didn\'t quite get that. Please text again.</Message></Response>'
				return HttpResponse(twiml, content_type='text/xml')
		
		# Handle "done" texts
		elif 'done' == text:
			# Person has completed task
			if person.status.lower() == "working":
				# Update DB
				person.status = 'Free'
				person.save(update_fields=['status'])
				task = Task.objects.get(volunteer=person.id, status="In Progress")
				task.status = 'Completed'
				task.save(update_fields=['status'])
				twiml = '<Response><Message>Thank you for completing the task: "' + task.description + '"!</Message></Response>'
				query = Volunteer.objects.filter(organizer = person.organizer, status = "Free")
				num_free = query.count()
				
				# Information for pusher
				data = {'event': event.id, 'num_free': num_free ,'id': person.id, 'name': person.name, 'status': person.status, 'task': task.id, 'taskstat': task.status, 'taskname': task.description, 'accept': person.num_accepted}
				x = 1
				for thing in query:
					data['volun' + str(x)] = thing.id
					data['volunname' + str(x)] = thing.name
					x = x + 1
				query = Task.objects.filter(organizer = person.organizer, status="Completed")
				x = 1
				for thing in query:
					data['task' + str(x)] = thing.id
					data['taskname'+str(x)] = thing.description
					x = x + 1
				data['numtasks'] = query.count()
				pusher_client.trigger('done', 'my-event', data)
				return HttpResponse(twiml, content_type='text/xml')
			
			else: 
				twiml = '<Response><Message>Didn\'t quite get that. Please text again.</Message></Response>'
				return HttpResponse(twiml, content_type='text/xml')
		
		# Handle "unavailable" or "no" texts
		elif 'unavailable' == text or 'no' == text: 
			# Case of free volunteer
			if 'unavailable' == text and person.status.lower() == "free": 
				person.status = 'Unavailable'
				person.save(update_fields=['status'])
				query = Volunteer.objects.filter(organizer = person.organizer, status = "Free")
				num_free = query.count()
				
				# Information for pusher
				data = {'pend': 0, 'event': event.id, 'num_free': num_free ,'id': person.id, 'name': person.name, 'status': person.status, 'accept': person.num_accepted}
				x = 1
				for thing in query:
					data['volun' + str(x)] = thing.id
					data['volunname' + str(x)] = thing.name
					x = x + 1
				query = Task.objects.filter(organizer = person.organizer, status="Completed")
				x = 1
				for thing in query:
					data['task' + str(x)] = thing.id
					data['taskname'+str(x)] = thing.description
					x = x + 1
				data['numtasks'] = query.count()
				pusher_client.trigger('unavailable', 'my-event', data)
				twiml = '<Response><Message>Your organizer knows you are temporarily unavailable. You MUST text back "available" when you are again.</Message></Response>'
				return HttpResponse(twiml, content_type='text/xml')
			
			# Case of working volunteer -- don't allow them to become unavailable
			elif 'unavailable' == text and person.status.lower() == "working": 
				twiml = '<Response><Message>Please complete your current task then reply that you are "unavailable".</Message></Response>'
				return HttpResponse(twiml, content_type='text/xml')
			
			# Case of pending volunteer -- reassign task
			elif person.status.lower() == "pending": 
				person.status = 'Unavailable'
				person.save(update_fields=['status'])
				task = Task.objects.get(volunteer=person, status="Pending")
				twiml = '<Response><Message>Your organizer knows you are temporarily unavailable, and the task has been reassigned. You MUST text back "available" when you are again.</Message></Response>'
				pusher_client.trigger('unavailable', 'my-event', {"num_free": 0, 'pend': 1, 'task': task.id,'event': event.id, 'id': person.id, 'name': person.name, 'status': person.status})
				reassign.apply_async((Task.objects.get(volunteer_id=person.id, status="Pending").id,), countdown=1)
				return HttpResponse(twiml, content_type='text/xml')
			
			else: 
				twiml = '<Response><Message>Didn\'t quite get that. Please text again.</Message></Response>'
				return HttpResponse(twiml, content_type='text/xml')
		
		# Handle "available" texts
		elif 'available' == text: 
			# Bring volunteer back into event
			if person.status.lower() == "unavailable": 
				t = Task.objects.filter(volunteer=person, status="Pending")
				if t: 
					person.status = 'Pending'
				else: 
					person.status = 'Free'
				person.save(update_fields=['status'])
				
				# may need to push other stuff
				query = Volunteer.objects.filter(organizer = person.organizer, status = "Free")
				num_free = query.count()

				if (t.count() > 0): 
					t = t[0].id
				else: 
					t = -1
				
				# Information for pusher
				data = {"task": t,'event': event.id, 'num_free': num_free ,'id': person.id, 'name': person.name, 'status': person.status, 'accept': person.num_accepted}
				x = 1
				for thing in query:
					data['volun' + str(x)] = thing.id
					data['volunname' + str(x)] = thing.name
					x = x + 1
				query = Task.objects.filter(organizer = person.organizer, status="Completed")
				x = 1
				for thing in query:
					data['task' + str(x)] = thing.id
					data['taskname'+str(x)] = thing.description
					x = x + 1
				data['numtasks'] = query.count()
				pusher_client.trigger('available', 'my-event', data)
				twiml = '<Response><Message>Your organizer knows that you are now available to work again!</Message></Response>'
				return HttpResponse(twiml, content_type='text/xml')
			
			else: 
				twiml = '<Response><Message>Didn\'t quite get that. Please text again.</Message></Response>'
				return HttpResponse(twiml, content_type='text/xml')

		# Do nothing for "start" or "unstop"
		elif 'start' == text or 'unstop' == text: 
			pass
		
		# Handle any other random messages
		else: 
			twiml = '<Response><Message>Didn\'t quite get that. Please text again.</Message></Response>'
			return HttpResponse(twiml, content_type='text/xml')
		return HttpResponseRedirect('/manage')
	
	except Event.DoesNotExist:
		return HttpResponseRedirect('/manage')
	except Volunteer.DoesNotExist:
		return HttpResponseRedirect('/manage')
	except Task.DoesNotExist:
		return HttpResponseRedirect('/manage')