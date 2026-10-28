# decorators.py
from functools import wraps
from flask import jsonify, g
from plans import PLANS, CREDIT_COSTS

def require_feature(feature_key):
    """Decorator to verify if the user's plan permits access to a specific feature."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_plan = getattr(g.user, 'plan_tier', 'free') # Default to free
            plan_config = PLANS.get(user_plan, PLANS["free"])
            
            if not plan_config["features"].get(feature_key, False):
                return jsonify({
                    "error": "Upgrade Required",
                    "message": f"This feature requires a Pro or Elite subscription.",
                    "upgrade_url": "/pricing"
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def deduct_credits(action_key):
    """Decorator to verify credit balance and deduct credits after successful execution."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cost = CREDIT_COSTS.get(action_key, 1)
            
            if g.user.credits_balance < cost:
                return jsonify({
                    "error": "Insufficient Credits",
                    "message": f"This action costs {cost} credits, but you only have {g.user.credits_balance} left.",
                    "topup_url": "/pricing#topup"
                }), 402  # 402 Payment Required
            
            # Execute the actual route controller
            response = f(*args, **kwargs)
            
            # Only deduct credits if request was successful (200 OK)
            if isinstance(response, tuple) and response[1] != 200:
                return response
                
            g.user.credits_balance -= cost
            db.session.commit() # Save credit reduction
            return response
        return decorated_function
    return decorator
