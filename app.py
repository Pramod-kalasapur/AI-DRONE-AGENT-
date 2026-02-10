from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
from google.generativeai import GenerativeModel, configure
from dateutil import parser
from datetime import datetime, date, timedelta
import json
import re
import os
import traceback

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"]
    }
})

# ==================== CONFIGURATION ====================

def load_config():
    """Load configuration from environment or config.json"""
    config = {
        'pilot_sheet_id': os.getenv('PILOT_SHEET_ID', '1Y-geekth_De4ktc-d1kih8m1LesLAKXUhRHKbdLi6ww'),
        'drone_sheet_id': os.getenv('DRONE_SHEET_ID', '1VlqJCLuPXYlC8aKzyMQmw2sTwa-AcLJod07E0-g49oY'),
        'credentials_file': os.getenv('CREDENTIALS_FILE', 'credentials.json'),
        'gemini_api_key': os.getenv('GEMINI_API_KEY', 'AIzaSyBkhs-3-GQ2fj9Q0Lkyzbjke52sAsaKT1U')
    }
    
    # Also try config.json as fallback
    try:
        with open('config.json', 'r') as f:
            file_config = json.load(f)
            config.update({k: v for k, v in file_config.items() if v})
    except:
        pass
    
    return config

CONFIG = load_config()

# ==================== GOOGLE SHEETS SETUP ====================

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    creds = Credentials.from_service_account_file(CONFIG['credentials_file'], scopes=scope)
    gsheet_client = gspread.authorize(creds)
    print("✅ Google Sheets connected")
except Exception as e:
    print(f"❌ Google Sheets error: {e}")
    gsheet_client = None

# ==================== GEMINI AI SETUP ====================

try:
    configure(api_key=CONFIG['gemini_api_key'])
    gemini_model = GenerativeModel('gemini-1.5-flash')
    print("✅ Gemini AI connected")
except Exception as e:
    print(f"❌ Gemini error: {e}")
    gemini_model = None

# ==================== DATA ACCESS LAYER ====================

PILOT_HEADERS = ['pilot_id', 'name', 'skills', 'certifications', 'location', 'status', 'current_assignment', 'available_from']
DRONE_HEADERS = ['drone_id', 'model', 'capabilities', 'status', 'location', 'current_assignment', 'maintenance_due']

def get_pilots():
    """Fetch all pilots from Google Sheet"""
    if not gsheet_client:
        return [], None
    try:
        sheet = gsheet_client.open_by_key(CONFIG['pilot_sheet_id']).sheet1
        records = sheet.get_all_records()
        return records, sheet
    except Exception as e:
        print(f"Error loading pilots: {e}")
        return [], None

def get_drones():
    """Fetch all drones from Google Sheet"""
    if not gsheet_client:
        return [], None
    try:
        sheet = gsheet_client.open_by_key(CONFIG['drone_sheet_id']).sheet1
        records = sheet.get_all_records()
        return records, sheet
    except Exception as e:
        print(f"Error loading drones: {e}")
        return [], None

def update_pilot_status(pilot_name, new_status, sheet=None):
    """Update pilot status in Google Sheet"""
    if not sheet:
        pilots, sheet = get_pilots()
    if not sheet:
        return False, "Cannot connect to sheet"
    
    try:
        for i, p in enumerate(pilots, start=2):
            if p['name'].lower() == pilot_name.lower():
                sheet.update_cell(i, 6, new_status)  # status column
                return True, f"Updated {pilot_name} to {new_status}"
        return False, f"Pilot {pilot_name} not found"
    except Exception as e:
        return False, str(e)

def update_drone_status(drone_id, new_status, sheet=None):
    """Update drone status in Google Sheet"""
    if not sheet:
        drones, sheet = get_drones()
    if not sheet:
        return False, "Cannot connect to sheet"
    
    try:
        for i, d in enumerate(drones, start=2):
            if str(d.get('drone_id', '')).upper() == drone_id.upper():
                sheet.update_cell(i, 4, new_status)  # status column
                return True, f"Updated {drone_id} to {new_status}"
        return False, f"Drone {drone_id} not found"
    except Exception as e:
        return False, str(e)

# ==================== INTELLIGENCE LAYER ====================

def is_available_today(pilot):
    """Check if pilot is available today"""
    status = str(pilot.get('status', '')).strip()
    if status not in ['Available', 'Standby']:
        return False
    avail_date_str = str(pilot.get('available_from', '')).strip()
    if not avail_date_str or avail_date_str in ['–', '-', 'None', '', 'Immediate']:
        return True
    try:
        avail_date = parser.parse(avail_date_str).date()
        return avail_date <= date.today()
    except:
        return True

def analyze_conflicts(pilots, drones):
    """Deep conflict analysis"""
    conflicts = {
        'critical': [],
        'warning': [],
        'info': []
    }
    
    # Double-booking pilots
    pilot_assignments = {}
    for p in pilots:
        assign = str(p.get('current_assignment', '')).strip()
        if assign and assign not in ['–', '-', 'None', '']:
            if assign in pilot_assignments:
                conflicts['critical'].append({
                    'type': 'PILOT_DOUBLE_BOOKING',
                    'message': f"Both {pilot_assignments[assign]['name']} and {p['name']} assigned to '{assign}'",
                    'pilots': [pilot_assignments[assign], p],
                    'assignment': assign
                })
            else:
                pilot_assignments[assign] = p
    
    # Double-booking drones
    drone_assignments = {}
    for d in drones:
        assign = str(d.get('current_assignment', '')).strip()
        if assign and assign not in ['–', '-', 'None', '']:
            if assign in drone_assignments:
                conflicts['critical'].append({
                    'type': 'DRONE_DOUBLE_BOOKING',
                    'message': f"Multiple drones assigned to '{assign}'",
                    'drones': [drone_assignments[assign], d],
                    'assignment': assign
                })
            else:
                drone_assignments[assign] = d
    
    # Location mismatches
    for p in pilots:
        p_assign = str(p.get('current_assignment', '')).strip()
        p_loc = str(p.get('location', '')).strip()
        if p_assign and p_assign not in ['–', '-', 'None', '']:
            for d in drones:
                d_assign = str(d.get('current_assignment', '')).strip()
                d_loc = str(d.get('location', '')).strip()
                if p_assign == d_assign and p_loc.lower() != d_loc.lower():
                    conflicts['warning'].append({
                        'type': 'LOCATION_MISMATCH',
                        'message': f"Location mismatch: Pilot {p['name']} in {p_loc} but Drone {d['model']} in {d_loc}",
                        'pilot': p,
                        'drone': d,
                        'assignment': p_assign
                    })
    
    # Maintenance issues
    for d in drones:
        d_status = str(d.get('status', '')).strip()
        d_assign = str(d.get('current_assignment', '')).strip()
        
        # Drone in maintenance but assigned
        if d_status == 'Maintenance' and d_assign and d_assign not in ['–', '-', 'None', '']:
            conflicts['critical'].append({
                'type': 'MAINTENANCE_CONFLICT',
                'message': f"{d['model']} is in maintenance but assigned to '{d_assign}'",
                'drone': d,
                'assignment': d_assign
            })
        
        # Maintenance overdue
        due_str = str(d.get('maintenance_due', '')).strip()
        if due_str and due_str not in ['–', '-', 'None', '']:
            try:
                due = parser.parse(due_str).date()
                days_overdue = (date.today() - due).days
                if days_overdue > 0:
                    conflicts['critical'].append({
                        'type': 'MAINTENANCE_OVERDUE',
                        'message': f"{d['model']} maintenance overdue by {days_overdue} days",
                        'drone': d,
                        'days_overdue': days_overdue
                    })
                elif days_overdue > -7:
                    conflicts['warning'].append({
                        'type': 'MAINTENANCE_SOON',
                        'message': f"{d['model']} maintenance due in {-days_overdue} days",
                        'drone': d,
                        'days_until': -days_overdue
                    })
            except:
                pass
    
    # Underutilized resources
    available_pilots = [p for p in pilots if is_available_today(p)]
    available_drones = [d for d in drones if d.get('status') == 'Available']
    
    if len(available_pilots) > len(pilots) * 0.5:
        conflicts['info'].append({
            'type': 'HIGH_AVAILABILITY',
            'message': f"{len(available_pilots)}/{len(pilots)} pilots available - consider new assignments"
        })
    
    return conflicts

def find_best_match(requirement, pilots, drones):
    """Find best pilot-drone match for a mission"""
    location = requirement.get('location', '').lower()
    skill = requirement.get('skill', '').lower()
    capability = requirement.get('capability', '').lower()
    urgency = requirement.get('urgency', 'normal')
    
    # Score pilots
    pilot_scores = []
    for p in pilots:
        if not is_available_today(p):
            continue
        
        score = 0
        reasons = []
        
        # Location match
        if location and location in p.get('location', '').lower():
            score += 30
            reasons.append(f"Located in {p['location']}")
        
        # Skill match
        if skill and skill in p.get('skills', '').lower():
            score += 40
            reasons.append(f"Has {skill} skills")
        
        # Certification bonus
        certs = p.get('certifications', '').lower()
        if 'advanced' in certs or 'master' in certs:
            score += 20
            reasons.append("Advanced certification")
        
        # Availability bonus
        if p.get('status') == 'Available':
            score += 10
            reasons.append("Immediately available")
        
        if score > 0:
            pilot_scores.append({
                'pilot': p,
                'score': score,
                'reasons': reasons
            })
    
    # Score drones
    drone_scores = []
    for d in drones:
        if d.get('status') != 'Available':
            continue
        
        score = 0
        reasons = []
        
        # Location match
        if location and location in d.get('location', '').lower():
            score += 30
            reasons.append(f"Located in {d['location']}")
        
        # Capability match
        if capability and capability in d.get('capabilities', '').lower():
            score += 40
            reasons.append(f"Has {capability} capability")
        
        # Maintenance check
        due_str = str(d.get('maintenance_due', '')).strip()
        if due_str and due_str not in ['–', '-', 'None', '']:
            try:
                due = parser.parse(due_str).date()
                days_until = (due - date.today()).days
                if days_until > 30:
                    score += 20
                    reasons.append("Maintenance OK (>30 days)")
                elif days_until > 7:
                    score += 10
                    reasons.append(f"Maintenance in {days_until} days")
            except:
                pass
        
        if score > 0:
            drone_scores.append({
                'drone': d,
                'score': score,
                'reasons': reasons
            })
    
    # Sort by score
    pilot_scores.sort(key=lambda x: x['score'], reverse=True)
    drone_scores.sort(key=lambda x: x['score'], reverse=True)
    
    return {
        'top_pilots': pilot_scores[:3],
        'top_drones': drone_scores[:3],
        'best_combo': {
            'pilot': pilot_scores[0] if pilot_scores else None,
            'drone': drone_scores[0] if drone_scores else None
        } if pilot_scores and drone_scores else None
    }

# ==================== GEMINI AI INTEGRATION ====================

def gemini_decision(context, question):
    """Get intelligent decision from Gemini AI"""
    if not gemini_model:
        return None, "Gemini AI not available"
    
    prompt = f"""You are an expert Drone Operations Coordinator AI. Analyze this operational data and provide intelligent recommendations.

OPERATIONAL CONTEXT:
{context}

USER QUESTION: {question}

Provide your response in this JSON format:
{{
    "analysis": "Brief situation analysis",
    "recommendation": "Primary recommendation with reasoning",
    "actions": ["Specific action 1", "Specific action 2"],
    "confidence": "High/Medium/Low",
    "risks": ["Potential risk 1", "Potential risk 2"]
}}

Be concise, professional, and actionable. Consider safety, efficiency, and resource optimization."""

    try:
        response = gemini_model.generate_content(prompt)
        # Extract JSON from response
        text = response.text
        # Find JSON block
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group()), None
        return {"analysis": text, "recommendation": "See analysis", "actions": [], "confidence": "Medium", "risks": []}, None
    except Exception as e:
        return None, str(e)

def gemini_chat_response(message, pilots, drones, conflicts):
    """Get contextual chat response from Gemini"""
    if not gemini_model:
        return None
    
    # Build context
    avail_pilots = len([p for p in pilots if is_available_today(p)])
    avail_drones = len([d for d in drones if d.get('status') == 'Available'])
    critical_issues = len(conflicts.get('critical', []))
    
    context = f"""
Current Operations Status:
- Total Pilots: {len(pilots)} (Available: {avail_pilots})
- Total Drones: {len(drones)} (Available: {avail_drones})
- Critical Issues: {critical_issues}
- Date: {date.today().strftime('%Y-%m-%d')}
"""

    if conflicts['critical']:
        context += "\nURGENT ISSUES:\n" + "\n".join([f"- {c['message']}" for c in conflicts['critical'][:3]])

    prompt = f"""You are Skylark Drone Operations AI Assistant. Respond to this user query naturally and helpfully.

{context}

USER: {message}

Provide a helpful, professional response. If there are critical issues, mention them. Be conversational but efficient."""

    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except:
        return None

# ==================== API ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health')
def health():
    pilots, _ = get_pilots()
    drones, _ = get_drones()
    return jsonify({
        'status': 'healthy',
        'google_sheets': gsheet_client is not None,
        'gemini_ai': gemini_model is not None,
        'pilots': len(pilots),
        'drones': len(drones),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/tables')
def get_tables():
    pilots, _ = get_pilots()
    drones, _ = get_drones()
    return jsonify({
        'pilots_html': html_table(pilots, PILOT_HEADERS),
        'drones_html': html_table(drones, DRONE_HEADERS)
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '').lower().strip()
    original_message = data.get('message', '').strip()
    
    # Get fresh data
    pilots, pilot_sheet = get_pilots()
    drones, drone_sheet = get_drones()
    
    if not pilots and not drones:
        return jsonify({
            'type': 'error',
            'content': '❌ Cannot connect to Google Sheets. Check configuration.'
        })
    
    # Analyze current state
    conflicts = analyze_conflicts(pilots, drones)
    
    # Extract intent and parameters
    intent = extract_intent(message)
    params = extract_params(message)
    
    response = {
        'type': 'text',
        'content': '',
        'actions_taken': [],
        'ai_analysis': None
    }
    
    # ==================== SMART DECISION COMMANDS ====================
    
    # AI Analysis & Recommendation
    if any(word in message for word in ['analyze', 'recommend', 'suggest', 'what should', 'best option', 'decide']):
        context = build_context(pilots, drones, conflicts)
        
        # Get Gemini decision
        gemini_result, error = gemini_decision(context, original_message)
        
        if gemini_result:
            response['type'] = 'decision'
            response['ai_analysis'] = gemini_result
            response['content'] = f"""🤖 **AI Analysis ({gemini_result['confidence']} Confidence)**

📊 **Situation:** {gemini_result['analysis']}

💡 **Recommendation:** {gemini_result['recommendation']}

✅ **Suggested Actions:**
{chr(10).join(['• ' + a for a in gemini_result['actions']])}

⚠️ **Risks to Consider:**
{chr(10).join(['• ' + r for r in gemini_result['risks']]) if gemini_result['risks'] else '• None identified'}"""
        else:
            response['content'] = f"AI analysis unavailable: {error}"
    
    # Smart Conflict Resolution
    elif intent == 'conflicts' or any(word in message for word in ['conflict', 'issue', 'problem', 'check']):
        if conflicts['critical']:
            # Get AI recommendation for resolution
            context = f"Critical conflicts: {json.dumps(conflicts['critical'], indent=2)}"
            gemini_result, _ = gemini_decision(context, "How should we resolve these conflicts?")
            
            response['type'] = 'urgent'
            response['content'] = format_conflicts_ai(conflicts, gemini_result)
            
            # Auto-suggest fixes
            response['suggested_fixes'] = generate_fixes(conflicts, pilots, drones)
        else:
            response['type'] = 'success'
            response['content'] = "✅ No critical issues. Operations running smoothly."
    
    # Smart Resource Matching
    elif intent == 'match' or any(word in message for word in ['assign', 'match', 'find', 'need', 'require']):
        match_result = find_best_match(params, pilots, drones)
        
        if match_result['best_combo']:
            combo = match_result['best_combo']
            pilot = combo['pilot']
            drone = combo['drone']
            
            # Get AI validation
            context = f"Recommended: Pilot {pilot['pilot']['name']} with Drone {drone['drone']['model']} for {params.get('skill', 'general')} mission in {params.get('location', 'unspecified')}"
            gemini_result, _ = gemini_decision(context, "Validate this assignment")
            
            response['content'] = f"""🔍 **Optimal Assignment Found**

👨‍✈️ **Recommended Pilot:** {pilot['pilot']['name']}
   Score: {pilot['score']}/100
   Why: {', '.join(pilot['reasons'])}

🚁 **Recommended Drone:** {drone['drone']['model']}
   Score: {drone['score']}/100
   Why: {', '.join(drone['reasons'])}

🤖 **AI Validation:** {gemini_result['recommendation'] if gemini_result else 'Assignment validated'}"""
            
            response['match_data'] = match_result
        else:
            response['content'] = "❌ No suitable matches found. Try adjusting requirements."
    
    # Smart Pilot Query
    elif intent == 'pilots':
        filtered = filter_pilots(pilots, params)
        
        # Get AI insights
        if filtered:
            context = f"Available pilots: {len(filtered)}. Top: {filtered[0]['name']} ({filtered[0].get('skills', 'N/A')})"
            insight, _ = gemini_decision(context, "Any insights about pilot availability?")
            
            response['content'] = f"""📋 **Pilot Roster** ({len(filtered)} found)

{format_pilot_list(filtered)}

💡 **AI Insight:** {insight['recommendation'] if insight else 'Standard availability'}"""
        else:
            response['content'] = "No pilots match your criteria."
        
        response['pilots_html'] = html_table(filtered, PILOT_HEADERS)
    
    # Smart Drone Query
    elif intent == 'drones':
        filtered = filter_drones(drones, params)
        
        if filtered:
            response['content'] = f"""🚁 **Fleet Status** ({len(filtered)} found)

{format_drone_list(filtered)}"""
        else:
            response['content'] = "No drones match your criteria."
        
        response['drones_html'] = html_table(filtered, DRONE_HEADERS)
    
    # Smart Update with Validation
    elif intent == 'update':
        result, msg = execute_update(message, pilots, drones, pilot_sheet, drone_sheet)
        response['type'] = 'success' if result else 'error'
        response['content'] = msg
        response['actions_taken'].append(msg)
    
    # Emergency/Urgent Mode
    elif intent == 'urgent' or any(word in message for word in ['emergency', 'urgent', 'critical', 'asap']):
        response['type'] = 'urgent'
        
        # Fast-track best available resources
        best = find_best_match({'urgency': 'critical', 'location': params.get('location')}, pilots, drones)
        
        context = f"URGENT REQUEST. Best available: Pilot {best['best_combo']['pilot']['pilot']['name'] if best['best_combo'] else 'NONE'}, Drone {best['best_combo']['drone']['drone']['model'] if best['best_combo'] else 'NONE'}"
        emergency_plan, _ = gemini_decision(context, "Create emergency response plan")
        
        response['content'] = f"""🚨 **EMERGENCY RESPONSE ACTIVATED**

{format_emergency_response(best, emergency_plan)}"""
    
    # Default: AI Chat Response
    else:
        # Try Gemini for natural response
        ai_response = gemini_chat_response(original_message, pilots, drones, conflicts)
        
        if ai_response:
            response['content'] = ai_response
        else:
            response['content'] = """🤖 I can help you with:

📊 **Analysis:** "Analyze our readiness for thermal mapping in Bangalore"
🔍 **Matching:** "Find best pilot-drone pair for LiDAR survey"
⚠️ **Conflicts:** "Check for scheduling conflicts"
🚨 **Emergency:** "Urgent: Need thermal capability in Mumbai ASAP"
📋 **Status:** "Available pilots with advanced certification"
✏️ **Updates:** "Update pilot Arjun to Deployed"

What do you need?"""
    
    # Always include fresh tables
    response['pilots_html'] = html_table(pilots, PILOT_HEADERS)
    response['drones_html'] = html_table(drones, DRONE_HEADERS)
    
    return jsonify(response)

# ==================== HELPER FUNCTIONS ====================

def extract_intent(message):
    """Extract user intent from message"""
    intents = {
        'pilots': ['pilot', 'pilots', 'roster', 'crew', 'operator'],
        'drones': ['drone', 'drones', 'fleet', 'uav', 'aircraft', 'inventory'],
        'conflicts': ['conflict', 'issue', 'problem', 'check', 'validate', 'verify'],
        'match': ['assign', 'match', 'find', 'need', 'require', 'suggest', 'recommend', 'best'],
        'update': ['update', 'change', 'set', 'mark', 'status'],
        'urgent': ['urgent', 'emergency', 'critical', 'asap', 'immediate', 'now']
    }
    
    for intent, keywords in intents.items():
        if any(k in message for k in keywords):
            return intent
    return 'chat'

def extract_params(message):
    """Extract parameters from message"""
    params = {}
    
    # Location
    locations = ['bangalore', 'mumbai', 'delhi', 'chennai', 'hyderabad', 'pune', 'kolkata']
    for loc in locations:
        if loc in message:
            params['location'] = loc.title()
            break
    
    # Skills/Capabilities
    skills = ['mapping', 'survey', 'thermal', 'lidar', 'inspection', 'rgb', 'multispectral', 'photography']
    for skill in skills:
        if skill in message:
            params['skill'] = skill.title()
            params['capability'] = skill.upper()
            break
    
    # Urgency
    if any(w in message for w in ['urgent', 'emergency', 'critical', 'asap']):
        params['urgency'] = 'critical'
    elif any(w in message for w in ['soon', 'tomorrow', 'next week']):
        params['urgency'] = 'high'
    
    return params

def filter_pilots(pilots, params):
    """Filter pilots by parameters"""
    result = [p for p in pilots if is_available_today(p)]
    
    if params.get('location'):
        result = [p for p in result if params['location'].lower() in p.get('location', '').lower()]
    
    if params.get('skill'):
        result = [p for p in result if params['skill'].lower() in p.get('skills', '').lower()]
    
    return result

def filter_drones(drones, params):
    """Filter drones by parameters"""
    result = [d for d in drones if d.get('status') == 'Available']
    
    if params.get('location'):
        result = [d for d in result if params['location'].lower() in d.get('location', '').lower()]
    
    if params.get('capability'):
        result = [d for d in result if params['capability'].lower() in d.get('capabilities', '').lower()]
    
    return result

def build_context(pilots, drones, conflicts):
    """Build operational context for AI"""
    avail_pilots = [p for p in pilots if is_available_today(p)]
    avail_drones = [d for d in drones if d.get('status') == 'Available']
    
    return f"""
Operational Status ({date.today().strftime('%Y-%m-%d')}):
- Pilots: {len(avail_pilots)}/{len(pilots)} available
- Drones: {len(avail_drones)}/{len(drones)} available
- Critical Issues: {len(conflicts['critical'])}
- Warnings: {len(conflicts['warning'])}

Available Pilots: {', '.join([p['name'] for p in avail_pilots[:5]])}
Available Drones: {', '.join([d['model'] for d in avail_drones[:5]])}

Critical Issues: {json.dumps([c['message'] for c in conflicts['critical']]) if conflicts['critical'] else 'None'}
"""

def execute_update(message, pilots, drones, pilot_sheet, drone_sheet):
    """Execute update command with validation"""
    # Pilot update
    pilot_names = [p['name'].lower() for p in pilots]
    for name in pilot_names:
        if name in message:
            # Extract status
            statuses = ['available', 'on leave', 'deployed', 'unavailable', 'standby', 'training']
            for status in statuses:
                if status in message:
                    success, msg = update_pilot_status(name.title(), status.title(), pilot_sheet)
                    return success, f"{'✅' if success else '❌'} {msg}"
            return False, "Status not recognized. Use: available, on leave, deployed, unavailable, standby, training"
    
    # Drone update
    drone_ids = [str(d.get('drone_id', '')).lower() for d in drones]
    for did in drone_ids:
        if did in message:
            statuses = ['available', 'maintenance', 'deployed', 'retired']
            for status in statuses:
                if status in message:
                    success, msg = update_drone_status(did.upper(), status.title(), drone_sheet)
                    return success, f"{'✅' if success else '❌'} {msg}"
            return False, "Status not recognized. Use: available, maintenance, deployed, retired"
    
    return False, "Could not identify pilot or drone to update"

def generate_fixes(conflicts, pilots, drones):
    """Generate suggested fixes for conflicts"""
    fixes = []
    
    for c in conflicts['critical']:
        if c['type'] == 'PILOT_DOUBLE_BOOKING':
            # Find replacement pilot
            avail = [p for p in pilots if is_available_today(p) and p['name'] not in [x['name'] for x in c['pilots']]]
            if avail:
                fixes.append(f"Reassign one pilot to {avail[0]['name']} ({avail[0]['location']})")
        
        elif c['type'] == 'DRONE_DOUBLE_BOOKING':
            avail = [d for d in drones if d.get('status') == 'Available' and d['model'] not in [x['model'] for x in c['drones']]]
            if avail:
                fixes.append(f"Use alternative drone: {avail[0]['model']}")
        
        elif c['type'] == 'MAINTENANCE_CONFLICT':
            avail = [d for d in drones if d.get('status') == 'Available' and d.get('location') == c['drone'].get('location')]
            if avail:
                fixes.append(f"Replace with {avail[0]['model']} from {avail[0]['location']}")
    
    return fixes

# ==================== FORMATTING ====================

def html_table(data, headers):
    """Generate HTML table"""
    if not data:
        return '<p class="no-data">No data available</p>'
    
    html = '<table class="data-table"><thead><tr>'
    for h in headers:
        html += f'<th>{h.replace("_", " ").title()}</th>'
    html += '</tr></thead><tbody>'
    
    for row in data:
        html += '<tr>'
        for h in headers:
            val = str(row.get(h, ''))
            # Status badges
            if h == 'status':
                badge_class = val.lower().replace(' ', '-')
                html += f'<td><span class="badge badge-{badge_class}">{val}</span></td>'
            else:
                html += f'<td>{val}</td>'
        html += '</tr>'
    
    html += '</tbody></table>'
    return html

def format_pilot_list(pilots):
    """Format pilot list"""
    if not pilots:
        return "No pilots found."
    lines = []
    for p in pilots[:5]:
        lines.append(f"• {p['name']} — {p.get('skills', 'N/A')} ({p.get('location', 'N/A')})")
    return '\n'.join(lines)

def format_drone_list(drones):
    """Format drone list"""
    if not drones:
        return "No drones found."
    lines = []
    for d in drones[:5]:
        lines.append(f"• {d['model']} — {d.get('capabilities', 'N/A')} ({d.get('location', 'N/A')})")
    return '\n'.join(lines)

def format_conflicts_ai(conflicts, gemini_result):
    """Format conflicts with AI insights"""
    lines = [f"⚠️ **{len(conflicts['critical'])} Critical Issues Found**\n"]
    
    for c in conflicts['critical']:
        icon = "🔴" if c['type'] in ['PILOT_DOUBLE_BOOKING', 'DRONE_DOUBLE_BOOKING', 'MAINTENANCE_CONFLICT'] else "🟠"
        lines.append(f"{icon} **{c['type'].replace('_', ' ')}**")
        lines.append(f"   {c['message']}\n")
    
    if conflicts['warning']:
        lines.append(f"\n🟡 **{len(conflicts['warning'])} Warnings**")
    
    if gemini_result:
        lines.append(f"\n🤖 **AI Resolution Strategy:**")
        lines.append(gemini_result.get('recommendation', 'Analyze manually'))
    
    return '\n'.join(lines)

def format_emergency_response(best_match, emergency_plan):
    """Format emergency response"""
    lines = []
    
    if best_match['best_combo']:
        p = best_match['best_combo']['pilot']
        d = best_match['best_combo']['drone']
        lines.append(f"⚡ **FASTEST DEPLOYMENT OPTION**")
        lines.append(f"")
        lines.append(f"👨‍✈️ **Pilot:** {p['pilot']['name']}")
        lines.append(f"   Location: {p['pilot'].get('location', 'Unknown')}")
        lines.append(f"   Skills: {p['pilot'].get('skills', 'N/A')}")
        lines.append(f"")
        lines.append(f"🚁 **Drone:** {d['drone']['model']}")
        lines.append(f"   Location: {d['drone'].get('location', 'Unknown')}")
        lines.append(f"   Capabilities: {d['drone'].get('capabilities', 'N/A')}")
    else:
        lines.append("❌ **NO IMMEDIATE RESOURCES AVAILABLE**")
    
    if emergency_plan:
        lines.append(f"\n📋 **Emergency Protocol:**")
        for action in emergency_plan.get('actions', []):
            lines.append(f"   • {action}")
    
    return '\n'.join(lines)

# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 70)
    print("SKYLARK DRONE OPERATIONS COORDINATOR AI")
    print("   Powered by Google Sheets + Gemini AI")
    print("=" * 70)
    print(f"📊 Google Sheets: {'✅ Connected' if gsheet_client else '❌ Failed'}")
    print(f"🤖 Gemini AI: {'✅ Connected' if gemini_model else '❌ Failed'}")
    print(f"📍 http://localhost:5000")
    print("=" * 70)
    app.run(debug=True, host='0.0.0.0', port=5000)