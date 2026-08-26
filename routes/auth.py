import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, current_user, login_required
from models import User
from extensions import db
from helpers import validate_password, generate_otp, send_reset_email
from datetime import datetime, timezone, timedelta

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        terms = request.form.get('terms')

        if not full_name or not email or not password:
            flash('Please fill out all required fields.', 'danger')
            return redirect(url_for('auth.register'))
            
        pwd_error = validate_password(password)
        if pwd_error:
            flash(pwd_error, 'danger')
            return redirect(url_for('auth.register'))
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.register'))
            
        if not terms:
            flash('You must accept the terms and conditions.', 'danger')
            return redirect(url_for('auth.register'))
            
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered. Please log in.', 'danger')
            return redirect(url_for('auth.register'))
            
        try:
            new_user = User(full_name=full_name, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('auth.register'))

    return render_template('auth/register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        flash('Logged in successfully.', 'success')
        
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
            
        return redirect(url_for('dashboard.dashboard'))

    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash('Please enter your email address.', 'danger')
            return redirect(url_for('auth.forgot_password'))
            
        user = User.query.filter_by(email=email).first()
        if user:
            otp = generate_otp()
            session['reset_email'] = email
            session['reset_otp'] = otp
            session['reset_expiry'] = (datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp()
            session['reset_attempts'] = 0
            session['reset_verified'] = False
            
            send_reset_email(email, otp)
            if not os.environ.get("MAIL_PASSWORD"):
                pass # Dev mode OTP banner removed
            
        flash('If an account exists for this email, a verification code has been sent.', 'info')
        return redirect(url_for('auth.verify_reset_code'))
        
    return render_template('auth/forgot_password.html')

@auth.route('/verify-reset-code', methods=['GET', 'POST'])
def verify_reset_code():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
        
    if 'reset_email' not in session or 'reset_otp' not in session:
        flash('Please request a password reset first.', 'warning')
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        
        # Check attempts
        attempts = session.get('reset_attempts', 0)
        if attempts >= 5:
            session.pop('reset_email', None)
            session.pop('reset_otp', None)
            session.pop('reset_expiry', None)
            session.pop('reset_attempts', None)
            flash('Too many failed attempts. Please request a new code.', 'danger')
            return redirect(url_for('auth.forgot_password'))
            
        # Check expiration
        expiry = session.get('reset_expiry', 0)
        if datetime.now(timezone.utc).timestamp() > expiry:
            flash('This verification code has expired. Please request a new code.', 'danger')
            return redirect(url_for('auth.verify_reset_code'))
            
        if code == session.get('reset_otp'):
            session['reset_verified'] = True
            flash('Code verified successfully.', 'success')
            return redirect(url_for('auth.reset_password'))
        else:
            session['reset_attempts'] = attempts + 1
            flash('Invalid verification code.', 'danger')
            
    return render_template('auth/verify_reset_code.html')
    
@auth.route('/resend-reset-code')
def resend_reset_code():
    if 'reset_email' not in session:
        return redirect(url_for('auth.forgot_password'))
        
    email = session['reset_email']
    otp = generate_otp()
    session['reset_otp'] = otp
    session['reset_expiry'] = (datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp()
    session['reset_attempts'] = 0
    session['reset_verified'] = False
    
    send_reset_email(email, otp)
    flash('A new verification code has been sent.', 'info')
    if not os.environ.get("MAIL_PASSWORD"):
        pass # Dev mode OTP banner removed
    return redirect(url_for('auth.verify_reset_code'))

@auth.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
        
    if not session.get('reset_verified'):
        flash('Please verify your reset code first.', 'warning')
        return redirect(url_for('auth.verify_reset_code'))
        
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        pwd_error = validate_password(password)
        if pwd_error:
            flash(pwd_error, 'danger')
            return redirect(url_for('auth.reset_password'))
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.reset_password'))
            
        email = session.get('reset_email')
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(password)
            db.session.commit()
            
        session.pop('reset_email', None)
        session.pop('reset_otp', None)
        session.pop('reset_expiry', None)
        session.pop('reset_attempts', None)
        session.pop('reset_verified', None)
        
        flash('Your password has been reset successfully. Please log in with your new password.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html')

