from flask import Flask, render_template, request, redirect

app = Flask(__name__)

# User Profile
USER = {
    "weight": 85,    # kg
    "height": 180,   # cm
    "age": 28,
    "gender": "male",
    "body_fat": 22   # Percentage
}

daily_logs = []

def calculate_katch_mcardle_bmr():
    """
    Calculates BMR based on Lean Body Mass.
    Formula: BMR = 370 + (21.6 * Lean Body Mass in kg)
    """
    weight = USER['weight']
    fat_percent = USER['body_fat']
    
    # Calculate Lean Body Mass (LBM)
    lbm = weight * (1 - (fat_percent / 100))
    
    # Katch-McArdle Formula
    bmr = 370 + (21.6 * lbm)
    return round(bmr, 0)

@app.route('/')
def home():
    bmr = calculate_katch_mcardle_bmr()
    return render_template('index.html', bmr=bmr, logs=daily_logs)

@app.route('/log', methods=['POST'])
def log_data():
    try:
        walk_km = float(request.form.get('walk', 0))
        consumed = float(request.form.get('consumed', 0))
        burnt = float(request.form.get('burnt', 0))
        
        bmr = calculate_katch_mcardle_bmr()
        total_burn = bmr + (walk_km * 60) + burnt
        deficit = total_burn - consumed
        
        fat_loss_g = (deficit / 7700) * 1000 if deficit > 0 else 0
        
        daily_logs.append({
            "walk": walk_km,
            "consumed": consumed,
            "burnt": burnt,
            "total_burn": round(total_burn, 0),
            "deficit": round(deficit, 0),
            "fat_loss": round(fat_loss_g, 2)
        })
    except ValueError:
        pass
    
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
