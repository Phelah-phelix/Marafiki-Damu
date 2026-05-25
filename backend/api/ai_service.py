import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
from decimal import Decimal
from .models import Contribution

class SavingsPredictor:
    @staticmethod
    def predict_future(member, weeks_ahead=4):
        contributions = Contribution.objects.filter(member=member).order_by('date')
        
        if contributions.count() < 3:
            return {
                'predicted_total': float(member.total_contributed) * 1.15,
                'confidence': 0.55,
                'trend': 'stable',
                'recommendation': '📈 Keep saving consistently! Your future looks bright.'
            }
        
        dates = []
        amounts = []
        start_date = contributions.first().date
        cumulative = Decimal('0')
        
        for contr in contributions:
            days_since_start = (contr.date - start_date).days
            dates.append(days_since_start)
            cumulative += contr.amount
            amounts.append(float(cumulative))
        
        X = np.array(dates).reshape(-1, 1)
        y = np.array(amounts)
        
        model = LinearRegression()
        model.fit(X, y)
        
        future_days = weeks_ahead * 7
        future_X = np.array([dates[-1] + future_days]).reshape(-1, 1)
        predicted = model.predict(future_X)[0]
        
        r_squared = model.score(X, y)
        
        slope = model.coef_[0]
        if slope > 1:
            trend = 'improving'
            recommendation = '🚀 Amazing progress! You\'re on fire! Keep this momentum!'
        elif slope < 0.5:
            trend = 'declining'
            recommendation = '⚠️ You can do better! Set daily reminders to save.'
        else:
            trend = 'stable'
            recommendation = '🎯 Good consistency! Try increasing by KES 10 daily.'
        
        return {
            'predicted_total': float(predicted),
            'confidence': round(r_squared, 2),
            'trend': trend,
            'recommendation': recommendation
        }
    
    @staticmethod
    def get_leaderboard_predictions(members):
        predictions = []
        for member in members:
            pred = SavingsPredictor.predict_future(member)
            predictions.append({
                'member_number': member.member_number,
                'username': member.user.username,
                'current_total': float(member.total_contributed),
                'predicted_4weeks': pred['predicted_total'],
                'trend': pred['trend']
            })
        return sorted(predictions, key=lambda x: x['predicted_4weeks'], reverse=True)