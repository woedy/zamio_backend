# bank_account/utils.py
from django.db import transaction
from decimal import Decimal
from collections import defaultdict
from django.utils import timezone
from .models import BankAccount, Transaction


class BulkBankOperations:
    """
    Utility class for handling bulk bank account operations efficiently
    for high-volume royalty payments
    """
    
    def __init__(self):
        self.pending_operations = []
        self.account_cache = {}
        
    def add_operation(self, operation_type, user, amount, description):
        """Add a bank operation to the pending queue"""
        self.pending_operations.append({
            'type': operation_type,  # 'deposit' or 'withdraw'
            'user': user,
            'amount': Decimal(str(amount)),
            'description': description
        })
    
    def execute_bulk_operations(self):
        """Execute all pending operations in bulk"""
        if not self.pending_operations:
            return {'success': 0, 'failed': 0, 'total_amount': Decimal('0')}
        
        # Group operations by user for efficiency
        user_operations = defaultdict(list)
        for op in self.pending_operations:
            user_operations[op['user']].append(op)
        
        success_count = 0
        failed_count = 0
        total_amount = Decimal('0')
        failed_operations = []
        
        with transaction.atomic():
            for user, operations in user_operations.items():
                try:
                    account, _ = BankAccount.objects.get_or_create(
                        user=user,
                        defaults={'balance': Decimal('0.00'), 'currency': 'Ghc'}
                    )
                    
                    # Calculate net change for this user
                    net_change = Decimal('0')
                    transactions_to_create = []
                    
                    for op in operations:
                        if op['type'] == 'deposit':
                            net_change += op['amount']
                            transactions_to_create.append(
                                Transaction(
                                    bank_account=account,
                                    transaction_type='Deposit',
                                    amount=op['amount'],
                                    description=op['description']
                                )
                            )
                        elif op['type'] == 'withdraw':
                            net_change -= op['amount']
                            transactions_to_create.append(
                                Transaction(
                                    bank_account=account,
                                    transaction_type='Withdrawal',
                                    amount=op['amount'],
                                    description=op['description']
                                )
                            )
                    
                    # Check if withdrawal operations are valid
                    if account.balance + net_change < 0:
                        # Handle insufficient funds
                        failed_operations.extend(operations)
                        failed_count += len(operations)
                        continue
                    
                    # Update account balance
                    account.balance += net_change
                    account.save()
                    
                    # Bulk create transactions
                    Transaction.objects.bulk_create(transactions_to_create)
                    
                    success_count += len(operations)
                    total_amount += sum(op['amount'] for op in operations if op['type'] == 'deposit')
                    
                except Exception as e:
                    failed_operations.extend(operations)
                    failed_count += len(operations)
                    print(f"Failed to process operations for user {user}: {e}")
        
        # Clear pending operations
        self.pending_operations = []
        
        return {
            'success': success_count,
            'failed': failed_count,
            'total_amount': total_amount,
            'failed_operations': failed_operations
        }
    
    def get_account_balance(self, user):
        """Get account balance efficiently with caching"""
        if user not in self.account_cache:
            account, _ = BankAccount.objects.get_or_create(
                user=user,
                defaults={'balance': Decimal('0.00'), 'currency': 'Ghc'}
            )
            self.account_cache[user] = account
        
        return self.account_cache[user].balance
    
    def ensure_station_funding(self, station_users, minimum_balance=Decimal('1000.00')):
        """Ensure station accounts have minimum funding for testing"""
        accounts_to_update = []
        
        for user in station_users:
            account, created = BankAccount.objects.get_or_create(
                user=user,
                defaults={'balance': minimum_balance, 'currency': 'Ghc'}
            )
            
            if not created and account.balance < minimum_balance:
                account.balance = minimum_balance
                accounts_to_update.append(account)
        
        if accounts_to_update:
            BankAccount.objects.bulk_update(accounts_to_update, ['balance'])
            
        return len(accounts_to_update)


class RoyaltyPaymentProcessor:
    """
    Specialized processor for royalty payments with batch optimization
    """
    
    def __init__(self):
        self.bulk_ops = BulkBankOperations()
        self.payment_summary = defaultdict(Decimal)
        
    def add_royalty_payment(self, artist_user, station_user, amount, track_title, station_name):
        """Add a royalty payment to the processing queue"""
        # Station withdrawal
        self.bulk_ops.add_operation(
            'withdraw', 
            station_user, 
            amount, 
            f"Royalty payment for '{track_title}'"
        )
        
        # Artist deposit
        self.bulk_ops.add_operation(
            'deposit', 
            artist_user, 
            amount, 
            f"Royalty for '{track_title}' from {station_name}"
        )
        
        # Track summary
        self.payment_summary[artist_user] += amount
    
    def process_all_payments(self):
        """Process all queued royalty payments"""
        result = self.bulk_ops.execute_bulk_operations()
        
        # Clear summary
        self.payment_summary.clear()
        
        return result
    
    def get_payment_summary(self):
        """Get summary of pending payments"""
        return dict(self.payment_summary)


# Example usage in the management command:
"""
# In your management command, replace individual payment processing with:

def process_royalty_payments_bulk(self, playlogs_data):
    processor = RoyaltyPaymentProcessor()
    
    # Queue all payments
    for data in playlogs_data:
        processor.add_royalty_payment(
            artist_user=data['artist_user'],
            station_user=data['station_user'],
            amount=data['royalty_amount'],
            track_title=data['track_title'],
            station_name=data['station_name']
        )
    
    # Process all payments at once
    result = processor.process_all_payments()
    
    return result
"""