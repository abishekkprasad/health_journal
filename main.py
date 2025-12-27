from flask import Flask, render_template, request, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from collections import defaultdict
import os

app = Flask(__name__)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///health_journal.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class UserProfile(db.Model):
    __tablename__ = 'user_profile'
    
    id = db.Column(db.Integer, primary_key=True)
    height = db.Column(db.Float)  # cm
    weight = db.Column(db.Float)  # kg
    body_fat = db.Column(db.Float)  # %
    age = db.Column(db.Integer)
    gender = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DailyLog(db.Model):
    __tablename__ = 'daily_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    weight = db.Column(db.Float, nullable=False)  # kg
    walk_km = db.Column(db.Float, default=0)
    consumed_calories = db.Column(db.Float, default=0)
    exercise_burnt = db.Column(db.Float, default=0)
    total_burn = db.Column(db.Float)
    deficit = db.Column(db.Float)
    fat_loss_g = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BodyFatHistory(db.Model):
    __tablename__ = 'body_fat_history'
    
    id = db.Column(db.Integer, primary_key=True)
    body_fat = db.Column(db.Float, nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

# Initialize database
def init_db():
    with app.app_context():
        db.create_all()

# Helper Functions
def get_user_profile():
    return UserProfile.query.first()

def calculate_katch_mcardle_bmr(weight, body_fat):
    """Calculate BMR using Katch-McArdle formula"""
    if weight is None or body_fat is None:
        return None
    lbm = weight * (1 - (body_fat / 100))
    bmr = 370 + (21.6 * lbm)
    return round(bmr, 0)

def get_weekly_summary():
    """Calculate weekly summaries from database"""
    logs = DailyLog.query.all()
    weekly = defaultdict(lambda: {"total_burn": 0, "consumed": 0, "deficit": 0, "fat_loss": 0, "days": 0})
    
    for log in logs:
        week_key = (log.date - timedelta(days=log.date.weekday())).strftime('%Y-%m-%d')
        weekly[week_key]["total_burn"] += log.total_burn or 0
        weekly[week_key]["consumed"] += log.consumed_calories or 0
        weekly[week_key]["deficit"] += log.deficit or 0
        weekly[week_key]["fat_loss"] += log.fat_loss_g or 0
        weekly[week_key]["days"] += 1
    
    return weekly

# Routes
@app.route('/')
def home():
    user = get_user_profile()
    
    if not user:
        return render_template('index.html', setup_needed=True)
    
    bmr = calculate_katch_mcardle_bmr(user.weight, user.body_fat)
    logs = DailyLog.query.order_by(DailyLog.date.desc()).all()
    weekly = get_weekly_summary()
    body_fat_history = BodyFatHistory.query.order_by(BodyFatHistory.recorded_at.desc()).limit(10).all()
    today = datetime.now().strftime('%Y-%m-%d')
    
    return render_template(
        'index.html',
        user=user,
        bmr=bmr,
        logs=logs,
        weekly=weekly,
        body_fat_history=body_fat_history,
        setup_needed=False,
        today=today
    )

@app.route('/setup', methods=['POST'])
def setup_profile():
    try:
        height = float(request.form.get('height'))
        weight = float(request.form.get('weight'))
        body_fat = float(request.form.get('body_fat'))
        age = int(request.form.get('age'))
        gender = request.form.get('gender')
        
        # Check if user profile already exists
        user = UserProfile.query.first()
        if user:
            user.height = height
            user.weight = weight
            user.body_fat = body_fat
            user.age = age
            user.gender = gender
        else:
            user = UserProfile(height=height, weight=weight, body_fat=body_fat, age=age, gender=gender)
            db.session.add(user)
        
        # Log the initial body fat
        body_fat_entry = BodyFatHistory(body_fat=body_fat)
        db.session.add(body_fat_entry)
        
        db.session.commit()
    except (ValueError, TypeError) as e:
        print(f"Error in setup: {e}")
    
    return redirect('/')

@app.route('/log', methods=['POST'])
def log_data():
    user = get_user_profile()
    if not user:
        return redirect('/')
    
    try:
        log_date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        log_date = datetime.strptime(log_date, '%Y-%m-%d').date()
        weight = float(request.form.get('weight', user.weight))
        walk_km = float(request.form.get('walk', 0))
        consumed = float(request.form.get('consumed', 0))
        burnt = float(request.form.get('burnt', 0))
        
        bmr = calculate_katch_mcardle_bmr(weight, user.body_fat)
        total_burn = bmr + (walk_km * 60) + burnt
        deficit = total_burn - consumed
        fat_loss_g = (deficit / 7700) * 1000 if deficit > 0 else 0
        
        # Check if log for this date exists
        existing_log = DailyLog.query.filter_by(date=log_date).first()
        if existing_log:
            existing_log.weight = weight
            existing_log.walk_km = walk_km
            existing_log.consumed_calories = consumed
            existing_log.exercise_burnt = burnt
            existing_log.total_burn = round(total_burn, 0)
            existing_log.deficit = round(deficit, 0)
            existing_log.fat_loss_g = round(fat_loss_g, 2)
        else:
            log = DailyLog(
                date=log_date,
                weight=weight,
                walk_km=walk_km,
                consumed_calories=consumed,
                exercise_burnt=burnt,
                total_burn=round(total_burn, 0),
                deficit=round(deficit, 0),
                fat_loss_g=round(fat_loss_g, 2)
            )
            db.session.add(log)
        
        db.session.commit()
    except (ValueError, TypeError) as e:
        print(f"Error logging data: {e}")
    
    return redirect('/')

@app.route('/update-body-fat', methods=['POST'])
def update_body_fat():
    user = get_user_profile()
    if not user:
        return redirect('/')
    
    try:
        new_body_fat = float(request.form.get('body_fat'))
        user.body_fat = new_body_fat
        
        # Log the body fat change
        body_fat_entry = BodyFatHistory(body_fat=new_body_fat)
        db.session.add(body_fat_entry)
        db.session.commit()
    except (ValueError, TypeError) as e:
        print(f"Error updating body fat: {e}")
    
    return redirect('/')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
