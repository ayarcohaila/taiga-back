# -*- coding: utf-8 -*-

from rest_framework import serializers
from greenmine.base.models import User


class UserLogged(object):
    def __init__(self, token, username, first_name, last_name, email, last_login, color, description, default_language, default_timezone, colorize_tags):
        self.token = token
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.last_login = last_login
        self.color = color
        self.description = description
        self.default_language = default_language
        self.default_timezone = default_timezone
        self.colorize_tags = colorize_tags


class LoginSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=40)
    username = serializers.CharField(max_length=30)
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    last_login = serializers.DateTimeField()
    color = serializers.CharField(max_length=9)
    description = serializers.CharField()
    default_language = serializers.CharField(max_length=20)
    default_timezone = serializers.CharField(max_length=20)
    colorize_tags = serializers.BooleanField()

    def restore_object(self, attrs, instance=None):
        """
        Given a dictionary of deserialized field values, either update
        an existing model instance, or create a new model instance.
        """
        if instance is not None:
            instance.token = attrs.get('token', None)
            instance.username = attrs.get('username', instance.username)
            instance.first_name = attrs.get('first_name', instance.first_name)
            instance.last_name = attrs.get('last_name', instance.last_name)
            instance.email = attrs.get('email', instance.email)
            instance.last_login = attrs.get('last_login', instance.last_login)
            instance.color = attrs.get('color', instance.color)
            instance.description = attrs.get('description', instance.description)
            instance.default_language = attrs.get('default_language', instance.default_language)
            instance.default_timezone = attrs.get('default_timezone', instance.default_timezone)
            instance.colorize_tags = attrs.get('colorize_tags', instance.colorize_tags)
            return instance
        return UserLogged(**attrs)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ('password',)
        #fields = ('id', 'username')
