from __future__ import absolute_import
from celery import shared_task
from twilio.rest import Client
from django.conf import settings
from .models import Volunteer, Task, Event
from random import randint
from django.utils import timezone
import pusher

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

# Runs when event must be ended
@shared_task
def end_event(event_id):
	try: 
		event = Event.objects.get(pk=event_id)
	except:
		return
	
	volunteers_end = Volunteer.objects.filter(organizer=event.organizer)
	from_ = settings.TWILIO_NUMBER
	body = 'Your organizer has ended the event ' + event.name + '. Thank you for volunteering!'
	
	# Message each volunteer
	for volunteer in volunteers_end: 
		to = volunteer.phone
		if not volunteer.unsubscribed:
			client.messages.create(to=to, from_=from_, body=body)
		else:
			pass
	
	# Delete from DB
	Volunteer.objects.filter(organizer=event.organizer).delete()
	Task.objects.filter(organizer=event.organizer).delete()
	event.delete()

# Sends reminder texts
@shared_task
def send_sms_reminder(task_id): 
	try: 
		task = Task.objects.get(pk=task_id)
	except: 
		return
	try: 
		volunteer = Volunteer.objects.get(pk=task.volunteer.id)
	except: 
		return
	
	# Send the text if still applicable
	if task.status.lower() == "pending" and volunteer.status.lower() == "pending": 
		body = 'Reminder from your organizer: "{0}"\n Please reply "yes" if you can or are doing the task!'.format(task.description)
		if not volunteer.unsubscribed:
			message = client.messages.create(
				body=body,
				to=task.volunteer.phone,
				from_=settings.TWILIO_NUMBER)

# Tries to reassign the task to someone else
@shared_task
def reassign(task_id): 
	try: 
		task = Task.objects.get(pk=task_id)
	except: 
		return 
	try: 
		volunteer_original = Volunteer.objects.get(pk=task.volunteer.id)
	except:
		return
	try: 
		event = Event.objects.get(organizer=volunteer_original.organizer)
	except:
		return
	
	if task.status.lower() == "pending": 
		other_volunteers = Volunteer.objects.filter(organizer=volunteer_original.organizer, status='Free').exclude(pk=volunteer_original.id)
		
		# Case where no one else to reassign to
		if not other_volunteers.exists(): 
			highP = event.highPriority
			lowP = event.lowPriority
			if task.priority: 
				reassign.apply_async((task_id,), countdown=highP)
				send_sms_reminder.apply_async((task_id,), countdown=highP)
				return
			else: 
				reassign.apply_async((task_id,), countdown=lowP)
				send_sms_reminder.apply_async((task_id,), countdown=lowP)
			return
		
		# Case where task can be reassigned
		else: 
			# Notify old volunteer
			if volunteer_original.status != "Unavailable": 
				body = 'The task has been reassigned. No need to reply. If you\'re temporarily unable to volunteer, reply "unavailable" to let your organizer know.'
				if not volunteer_original.unsubscribed:
					message = client.messages.create(
						body=body,
						to=task.volunteer.phone,
						from_=settings.TWILIO_NUMBER)
				volunteer_original.status = "Free"
				volunteer_original.save()
			
			# Update new volunteer
			new_volunteer = other_volunteers[randint(0, len(other_volunteers)-1)]
			to = new_volunteer.phone
			from_ = settings.TWILIO_NUMBER
			body = 'From your organizer: "' + task.description + '"\nReply "yes" if you can do the task!'
			if not new_volunteer.unsubscribed:
				client.messages.create(to=to, from_=from_, body=body)
			new_volunteer.status = "Pending"
			if task.first and new_volunteer.num_assigned < settings.PSIF_MAX: 
				new_volunteer.num_assigned += 1
			new_volunteer.latest_assignment = timezone.now()
			new_volunteer.save()
			
			# Cleanup work
			new_task = Task.objects.create(organizer=task.organizer, volunteer=new_volunteer, description=task.description, priority=task.priority, first=False)
			if task.first and event.total_reassigned < settings.PSIF_MAX: 
				event.total_reassigned += 1
				event.save()
			task.delete()
			query = Volunteer.objects.filter(organizer = task.organizer, status = "Free")
			num_free = query.count()
				
			# Information for pusher
			data = {'event': event.id, 'num_free': num_free, 'nphone': new_volunteer.phone,'otaskname': new_task.description, 'ntask': task_id,'hp': new_task.priority,'otask': new_task.id,'old': volunteer_original.id, 'new': new_volunteer.id, 'ostatus': volunteer_original.status, 'nstatus': new_volunteer.status, 'oname': volunteer_original.name, 'nname': new_volunteer.name}
			x = 1
			for thing in query:
				data['volun' + str(x)] = thing.id
				data['volunname' + str(x)] = thing.name
				x = x + 1
			query = Task.objects.filter(organizer = task.organizer, status="Completed")
			x = 1
			for thing in query:
				data['task' + str(x)] = thing.id
				data['taskname'+str(x)] = thing.description
				x = x + 1
			data['numtasks'] = query.count()
			pusher_client.trigger('reassign', 'my-event', data)