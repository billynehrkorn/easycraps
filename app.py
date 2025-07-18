from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import random
import os

app = Flask(__name__)
CORS(app)

# Global balance tracking (in a real app, you'd use a database)
player_balance = 500
last_bet_total = 0  # Global to track total bet of last round
last_win_amount = 0 # Global to track net win/loss of last round


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/roll', methods=['POST'])
def roll_dice():
    global player_balance, last_bet_total, last_win_amount

    data = request.json
    bets = data.get('bets', {})

    # Generate two dice
    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    dice_sum = d1 + d2

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

    # Update global last roll stats
    last_bet_total = total_stakes
    last_win_amount = net_change

    return jsonify({
        'dice': [d1, d2],
        'sum': dice_sum,
        'results': results,
        'newBalance': player_balance,
        'totalStakesThisRound': total_stakes,
        'netChangeThisRound': net_change
    })


@app.route('/balance')
def get_balance():
    return jsonify({'balance': player_balance})

@app.route('/game_stats') # New endpoint to get all game stats
def get_game_stats():
    global player_balance, last_bet_total, last_win_amount
    return jsonify({
        'balance': player_balance,
        'lastBetTotal': last_bet_total,
        'lastWinAmount': last_win_amount
    })


@app.route('/static/<filename>')
def static_files(filename):
    return send_from_directory('static', filename)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
