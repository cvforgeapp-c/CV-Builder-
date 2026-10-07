import os
import stripe
from flask import Blueprint, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from models import db, User

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@billing_bp.route('/checkout')
@login_required
def checkout():
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        customer_email=current_user.email,
        line_items=[{
            'price': os.getenv("STRIPE_PREMIUM_PRICE_ID"),
            'quantity': 1,
        }],
        mode='subscription',
        success_url=url_for('billing.success', _external=True),
        cancel_url=url_for('billing.cancel', _external=True),
    )
    return redirect(session.url, code=330)

@billing_bp.route('/success')
def success():
    return render_template('billing/success.html')

@billing_bp.route('/cancel')
def cancel():
    return render_template('billing/cancel.html')

@billing_bp.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET"))
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    if event['type'] == 'customer.subscription.created':
        sub = event['data']['object']
        user = User.query.filter_by(email=sub.get('customer_email')).first()
        if user:
            user.is_premium = True
            user.subscription_status = "active"
            user.stripe_subscription_id = sub['id']
            db.session.commit()

    elif event['type'] == 'customer.subscription.deleted':
        sub = event['data']['object']
        user = User.query.filter_by(stripe_subscription_id=sub['id']).first()
        if user:
            user.is_premium = False
            user.subscription_status = "canceled"
            db.session.commit()

    return jsonify({'status': 'success'}), 200
