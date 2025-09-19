from django.core.management.base import BaseCommand
from disputes.models import DisputeWorkflowRule, DisputeStatus


class Command(BaseCommand):
    help = 'Set up default dispute workflow rules'
    
    def handle(self, *args, **options):
        """
        Create default workflow rules for dispute state transitions
        """
        rules = [
            # From SUBMITTED
            {
                'from_status': DisputeStatus.SUBMITTED,
                'to_status': DisputeStatus.UNDER_REVIEW,
                'required_role': 'admin',
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': False
            },
            {
                'from_status': DisputeStatus.SUBMITTED,
                'to_status': DisputeStatus.REJECTED,
                'required_role': 'admin',
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': False,
                'notify_stakeholders': False
            },
            
            # From UNDER_REVIEW
            {
                'from_status': DisputeStatus.UNDER_REVIEW,
                'to_status': DisputeStatus.EVIDENCE_REQUIRED,
                'required_role': '',  # Any authorized user
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': False
            },
            {
                'from_status': DisputeStatus.UNDER_REVIEW,
                'to_status': DisputeStatus.MEDIATION,
                'required_role': 'admin',
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': True
            },
            {
                'from_status': DisputeStatus.UNDER_REVIEW,
                'to_status': DisputeStatus.RESOLVED,
                'required_role': '',  # Any authorized user
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': True
            },
            {
                'from_status': DisputeStatus.UNDER_REVIEW,
                'to_status': DisputeStatus.REJECTED,
                'required_role': 'admin',
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': False
            },
            
            # From EVIDENCE_REQUIRED
            {
                'from_status': DisputeStatus.EVIDENCE_REQUIRED,
                'to_status': DisputeStatus.UNDER_REVIEW,
                'required_role': '',  # Any authorized user
                'requires_evidence': True,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': False
            },
            {
                'from_status': DisputeStatus.EVIDENCE_REQUIRED,
                'to_status': DisputeStatus.REJECTED,
                'required_role': 'admin',
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': False
            },
            
            # From MEDIATION
            {
                'from_status': DisputeStatus.MEDIATION,
                'to_status': DisputeStatus.RESOLVED,
                'required_role': 'admin',
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': True
            },
            {
                'from_status': DisputeStatus.MEDIATION,
                'to_status': DisputeStatus.ESCALATED,
                'required_role': 'admin',
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': True
            },
            
            # From ESCALATED
            {
                'from_status': DisputeStatus.ESCALATED,
                'to_status': DisputeStatus.RESOLVED,
                'required_role': 'admin',
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': True
            },
            {
                'from_status': DisputeStatus.ESCALATED,
                'to_status': DisputeStatus.EXTERNAL_ARBITRATION,
                'required_role': 'admin',
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': True
            },
            
            # From EXTERNAL_ARBITRATION
            {
                'from_status': DisputeStatus.EXTERNAL_ARBITRATION,
                'to_status': DisputeStatus.RESOLVED,
                'required_role': 'admin',
                'requires_evidence': False,
                'auto_transition': False,
                'notify_submitter': True,
                'notify_assigned': True,
                'notify_stakeholders': True
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for rule_data in rules:
            rule, created = DisputeWorkflowRule.objects.get_or_create(
                from_status=rule_data['from_status'],
                to_status=rule_data['to_status'],
                defaults=rule_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created rule: {rule.from_status} -> {rule.to_status}'
                    )
                )
            else:
                # Update existing rule with new data
                for key, value in rule_data.items():
                    setattr(rule, key, value)
                rule.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'Updated rule: {rule.from_status} -> {rule.to_status}'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully set up dispute workflow rules. '
                f'Created: {created_count}, Updated: {updated_count}'
            )
        )