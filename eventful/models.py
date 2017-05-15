from __future__ import unicode_literals, absolute_import
from django.db import models
from django.db.models import F
from django.contrib.auth.models import User
from datetime import datetime
from django.conf import settings
from django.utils.encoding import python_2_unicode_compatible
from django.utils import timezone

class Event(models.Model): 
	organizer = models.OneToOneField(User, on_delete=models.CASCADE)
	name = models.TextField('Name')
	end = models.DateTimeField('End Date')
	total_assigned = models.PositiveSmallIntegerField('Total Number Of Tasks Assigned', default=0)
	total_reassigned = models.PositiveSmallIntegerField('Total Number Of Tasks Reassigned', default=0)
	total_accepted = models.PositiveSmallIntegerField('Total Number Of Tasks Accepted', default=0)
	highPriority = models.PositiveSmallIntegerField('High', default=60)
	lowPriority = models.PositiveSmallIntegerField('Low', default=120)

	def schedule_end(self):
		from .tasks import end_event
		end_event.apply_async((self.id,), eta=self.end + timezone.timedelta(hours=36))
	
	def save(self, *args, **kwargs): 
		first = self.pk is None
		super(Event, self).save(*args, **kwargs)
		if first:
			self.schedule_end()

@python_2_unicode_compatible
class Volunteer(models.Model): 
	organizer = models.ForeignKey(User, on_delete=models.CASCADE)
	name = models.TextField('Name')
	phone = models.TextField('Phone Number', unique=True)
	category = models.TextField('Category (Optional)', null=True, blank=True, default='')
	status = models.TextField('Status', default='Free')
	num_assigned = models.PositiveSmallIntegerField('Number Of Tasks Assigned', default=0)
	num_accepted = models.PositiveSmallIntegerField('Number Of Tasks Accepted', default=0)
	avg_responsetime = models.PositiveIntegerField('Average Response Time', default=0)
	latest_assignment = models.DateTimeField('Time of Latest Assignment', default=timezone.now)
	unsubscribed = models.BooleanField('Unsubscribed', default=False)

	class Meta: 
		unique_together = (('organizer', 'name'), ('organizer', 'phone'))

	def __str__(self):
		return self.name

class Task(models.Model): 
	organizer = models.ForeignKey(User, on_delete=models.CASCADE)
	volunteer = models.ForeignKey(Volunteer, null=True, on_delete=models.SET_NULL)
	description = models.TextField('Description')
	priority = models.BooleanField('High Priority')
	status = models.TextField('Status', default='Pending')
	first = models.BooleanField('First Instance', default=True)
	
	def schedule_reminder(self):
		from .tasks import send_sms_reminder, reassign
		event = Event.objects.get(organizer=self.organizer)
		
		if self.priority:
			send_sms_reminder.apply_async((self.id,), countdown=event.highPriority)
			send_sms_reminder.apply_async((self.id,), countdown=2*event.highPriority)
			reassign.apply_async((self.id,), countdown=3*event.highPriority)
		
		else: 
			send_sms_reminder.apply_async((self.id,), countdown=event.lowPriority)
			send_sms_reminder.apply_async((self.id,), countdown=2*event.lowPriority)
			reassign.apply_async((self.id,), countdown=3*event.lowPriority)

	def save(self, *args, **kwargs):
		first = self.pk is None
		if first: 
			if not Task.objects.filter(organizer=self.organizer, volunteer=self.volunteer, status="Pending"):
				super(Task, self).save(*args, **kwargs)
				self.schedule_reminder()
		else: 
			super(Task, self).save(*args, **kwargs)