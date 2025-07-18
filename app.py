from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import random
import os
import csv
from datetime import datetime

app = Flask(__name__)
CORS(app)

# In-memory store for session balances and last game stats
# In a real application, this would be persisted in a database
session_data = {}  # {session_id: {'balance': 500, 'lastBetTotal': 0, 'lastWinAmount': 0}}


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/roll', methods=['POST'])
def roll_dice():
    data = request.json
    session_id = data.get('sessionId')
    bets = data.get('bets', {})

    # Initialize session data if it doesn't exist
    if session_id not in session_data:
        session_data[session_id] = {'balance': 500, 'lastBetTotal': 0, 'lastWinAmount': 0}

    current_session = session_data[session_id]
    player_balance = current_session['balance']

    # Generate two dice
    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    dice_sum = d1 + d2

    # Log the roll to rolls.csv
    with open(os.path.join(app.root_path, 'rolls.csv'), 'a', newline='') as f:
        writer = csv.writer(f)
        # Write header if file is new/empty (optional, but good practice for first run)
        if f.tell() == 0:
            writer.writerow(['timestamp', 'die1', 'die2', 'sum'])
        writer.writerow([datetime.now().isoformat(), d1, d2, dice_sum])

    results = {}
    total_stakes = 0
    total_payouts = 0

    # Process individual number bets (2, 3, 4, 5, 6, 8, 9, 10, 11, 12)
    individual_numbers = [2, 3, 4, 5, 6, 8, 9, 10, 11, 12]
    payout_ratios = {
        2: 11 / 2, 12: 11 / 2,  # 5.5:1
        3: 11 / 4, 11: 11 / 4,  # 2.75:1
        4: 9 / 5, 10: 9 / 5,  # 1.8:1
        5: 7 / 5, 9: 7 / 5,  # 1.4:1
        6: 7 / 6, 8: 7 / 6  # 1.167:1
    }

    for num in individual_numbers:
        bet_amount = float(bets.get(str(num), 0))
        if bet_amount > 0:
            if dice_sum == num:
                # Win: pay out at the specified ratio
                win = True
                push = False
                payout = bet_amount * payout_ratios[num]
                total_stakes += bet_amount  # Add original stake to stakes
                total_payouts += payout + bet_amount  # Add payout + returned stake
            elif dice_sum == 7:
                # Loss: lose the stake
                win = False
                push = False
                payout = 0
                total_stakes += bet_amount  # Lose the stake
            else:
                # Push: return original stake (no net change to balance)
                win = False
                push = True
                payout = bet_amount  # Return original stake
            # Don't add to total_stakes or total_payouts since it's a wash

            results[str(num)] = {
                'bet': bet_amount,
                'payout': payout,
                'win': win,
                'push': push
            }

    # Process field bet - FIXED LOGIC
    field_bet = float(bets.get('field', 0))
    if field_bet > 0:
        total_stakes += field_bet
        if dice_sum in [2, 12]:
            # 2 and 12 pay 2 to 1
            field_payout = field_bet + (field_bet * 2)  # Return stake + 2:1 payout
            field_win = True
        elif dice_sum in [3, 4, 9, 10, 11]:
            # 3, 4, 9, 10, 11 pay 1 to 1
            field_payout = field_bet + (field_bet * 1)  # Return stake + 1:1 payout
            field_win = True
        else:
            # All other numbers lose
            field_payout = 0
            field_win = False

        total_payouts += field_payout
        results['field'] = {
            'bet': field_bet,
            'payout': field_payout,
            'win': field_win,
            'push': False
        }

    # Process low field bet (2/3/4) - pays 9:2
    low_field_bet = float(bets.get('lowField', 0))
    if low_field_bet > 0:
        total_stakes += low_field_bet
        low_field_win = dice_sum in [2, 3, 4]
        low_field_payout = low_field_bet + (low_field_bet * (9 / 2)) if low_field_win else 0
        total_payouts += low_field_payout

        results['lowField'] = {
            'bet': low_field_bet,
            'payout': low_field_payout,
            'win': low_field_win,
            'push': False
        }

    # Process high field bet (10/11/12) - pays 9:2
    high_field_bet = float(bets.get('highField', 0))
    if high_field_bet > 0:
        total_stakes += high_field_bet
        high_field_win = dice_sum in [10, 11, 12]
        high_field_payout = high_field_bet + (high_field_bet * (9 / 2)) if high_field_win else 0
        total_payouts += high_field_payout

        results['highField'] = {
            'bet': high_field_bet,
            'payout': high_field_payout,
            'win': high_field_win,
            'push': False
        }

    # Process seven bet (pays 21:5 on 7)
    seven_bet = float(bets.get('seven', 0))
    if seven_bet > 0:
        total_stakes += seven_bet
        seven_win = dice_sum == 7
        seven_payout = seven_bet + (seven_bet * (21 / 5)) if seven_win else 0
        total_payouts += seven_payout

        results['seven'] = {
            'bet': seven_bet,
            'payout': seven_payout,
            'win': seven_win,
            'push': False
        }

    # Calculate net change and update balance
    net_change = total_payouts - total_stakes
    player_balance += net_change
    current_session['balance'] = player_balance  # Update session balance

    # Update session last roll stats
    current_session['lastBetTotal'] = total_stakes
    current_session['lastWinAmount'] = net_change

    return jsonify({
        'dice': [d1, d2],
        'sum': dice_sum,
        'results': results,
        'newBalance': player_balance,  # Send back the updated balance
        'totalStakesThisRound': total_stakes,
        'netChangeThisRound': net_change
    })


@app.route('/game_stats', methods=['GET'])
def get_game_stats():
    session_id = request.args.get('sessionId')  # Get session ID from query parameter
    if session_id not in session_data:
        session_data[session_id] = {'balance': 500, 'lastBetTotal': 0, 'lastWinAmount': 0}

    current_session = session_data[session_id]
    return jsonify({
        'balance': current_session['balance'],
        'lastBetTotal': current_session['lastBetTotal'],
        'lastWinAmount': current_session['lastWinAmount']
    })


@app.route('/static/<filename>')
def static_files(filename):
    return send_from_directory('static', filename)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
