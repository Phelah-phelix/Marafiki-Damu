from rest_framework import serializers
from django.contrib.auth.models import User
from decimal import Decimal
from .models import ChamaGroup, GroupAdmin, Member, Contribution, WeeklyProgress, AI_Prediction

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class ChamaGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChamaGroup
        fields = '__all__'

class MemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    
    class Meta:
        model = Member
        fields = ['id', 'member_number', 'user', 'username', 'password', 'email', 
                  'phone_number', 'id_number', 'location', 'occupation', 
                  'status', 'total_contributed', 'joined_at', 'group']
    
    def create(self, validated_data):
        username = validated_data.pop('username')
        password = validated_data.pop('password')
        email = validated_data.pop('email')
        
        user = User.objects.create_user(username=username, password=password, email=email)
        member = Member.objects.create(user=user, **validated_data)
        return member

class ContributionSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.user.username', read_only=True)
    member_number = serializers.IntegerField(source='member.member_number', read_only=True)
    
    class Meta:
        model = Contribution
        fields = ['id', 'member', 'member_number', 'member_name', 'amount', 
                  'date', 'transaction_id', 'payment_method', 'created_at', 'group']

class WeeklyProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyProgress
        fields = '__all__'

class AIPredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AI_Prediction
        fields = '__all__'