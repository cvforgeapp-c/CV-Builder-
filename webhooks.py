# webhooks.py

@webhooks_bp.route('/api/webhook/payment', methods=['POST'])
def handle_payment_webhook():
    event = request.json
    
    # Handle Successful Subscription Purchase / Renewal
    if event['type'] == 'subscription.updated' or event['type'] == 'checkout.completed':
        user_id = event['data']['custom_metadata']['user_id']
        purchased_plan = event['data']['plan_code'] # 'pro' or 'elite'
        
        user = User.query.get(user_id)
        user.plan_tier = purchased_plan
        user.credits_balance += PLANS[purchased_plan]["monthly_credits"]
        db.session.commit()
        
    return jsonify({"received": True}), 200
