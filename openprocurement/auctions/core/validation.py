# -*- coding: utf-8 -*-
from openprocurement.api.models import get_now
from openprocurement.api.utils import error_handler
from openprocurement.api.utils import update_logging_context
from openprocurement.api.validation import (
    validate_json_data,
    validate_data,
    validate_file_update,
    validate_file_upload,
    validate_patch_document_data,
)


def raise_wrapper(func):
    def wrapper(*args, **kw):
        res = func(*args, **kw)
        request = args[0]
        if request.errors:
            raise error_handler(args[0])
        else:
            return res

    return wrapper

validate_data = raise_wrapper(validate_data)
validate_json_data = raise_wrapper(validate_json_data)
validate_file_update = raise_wrapper(validate_file_update)
validate_file_upload = raise_wrapper(validate_file_upload)
validate_patch_document_data = raise_wrapper(validate_patch_document_data)


def validate_auction_data(request, **kwargs):
    update_logging_context(request, {'auction_id': '__new__'})
    data = validate_json_data(request)
    if data is None:
        raise error_handler(request)

    model = request.auction_from_data(data, create=False)
    if not request.check_accreditation(model.create_accreditation):
        request.errors.add('procurementMethodType', 'accreditation', 'Broker Accreditation level does not permit auction creation')
        request.errors.status = 403
        raise error_handler(request)
    data = validate_data(request, model, data=data)
    if data and data.get('mode', None) is None and request.check_accreditation('t'):
        request.errors.add('procurementMethodType', 'mode', 'Broker Accreditation level does not permit auction creation')
        request.errors.status = 403
        raise error_handler(request)


def validate_patch_auction_data(request, **kwargs):
    data = validate_json_data(request)
    if data is None:
        raise error_handler(request)
    if request.context.status != 'draft':
        # import pdb; pdb.set_trace();
        return validate_data(request, type(request.auction), True, data)
    default_status = type(request.auction).fields['status'].default
    if data.get('status') != default_status:
        request.errors.add('body', 'data', 'Can\'t update auction in current (draft) status')
        request.errors.status = 403
        raise error_handler(request)
    request.validated['data'] = {'status': default_status}
    request.context.status = default_status


def validate_auction_auction_data(request, **kwargs):
    data = validate_patch_auction_data(request)
    auction = request.validated['auction']
    if auction.status != 'active.auction':
        request.errors.add('body', 'data', 'Can\'t {} in current ({}) auction status'.format('report auction results' if request.method == 'POST' else 'update auction urls', auction.status))
        request.errors.status = 403
        raise error_handler(request)
    lot_id = request.matchdict.get('auction_lot_id')
    if auction.lots and any([i.status != 'active' for i in auction.lots if i.id == lot_id]):
        request.errors.add('body', 'data', 'Can {} only in active lot status'.format('report auction results' if request.method == 'POST' else 'update auction urls'))
        request.errors.status = 403
        raise error_handler(request)
    if data is not None:
        bids = data.get('bids', [])
        auction_bids_ids = [i.id for i in auction.bids]
        if len(bids) != len(auction.bids):
            request.errors.add('body', 'bids', "Number of auction results did not match the number of auction bids")
            request.errors.status = 422
            raise error_handler(request)
        if set([i['id'] for i in bids]) != set(auction_bids_ids):
            request.errors.add('body', 'bids', "Auction bids should be identical to the auction bids")
            request.errors.status = 422
            raise error_handler(request)
        data['bids'] = [x for (y, x) in sorted(zip([auction_bids_ids.index(i['id']) for i in bids], bids))]
        if data.get('lots'):
            auction_lots_ids = [i.id for i in auction.lots]
            if len(data.get('lots', [])) != len(auction.lots):
                request.errors.add('body', 'lots', "Number of lots did not match the number of auction lots")
                request.errors.status = 422
                raise error_handler(request)
            if set([i['id'] for i in data.get('lots', [])]) != set([i.id for i in auction.lots]):
                request.errors.add('body', 'lots', "Auction lots should be identical to the auction lots")
                request.errors.status = 422
                raise error_handler(request)
            data['lots'] = [
                x if x['id'] == lot_id else {}
                for (y, x) in sorted(zip([auction_lots_ids.index(i['id']) for i in data.get('lots', [])], data.get('lots', [])))
            ]
        if auction.lots:
            for index, bid in enumerate(bids):
                if (getattr(auction.bids[index], 'status', 'active') or 'active') == 'active':
                    if len(bid.get('lotValues', [])) != len(auction.bids[index].lotValues):
                        request.errors.add('body', 'bids', [{u'lotValues': [u'Number of lots of auction results did not match the number of auction lots']}])
                        request.errors.status = 422
                        raise error_handler(request)
                    for lot_index, lotValue in enumerate(auction.bids[index].lotValues):
                        if lotValue.relatedLot != bid.get('lotValues', [])[lot_index].get('relatedLot', None):
                            request.errors.add('body', 'bids', [{u'lotValues': [{u'relatedLot': ['relatedLot should be one of lots of bid']}]}])
                            request.errors.status = 422
                            raise error_handler(request)
            for bid_index, bid in enumerate(data['bids']):
                if 'lotValues' in bid:
                    bid['lotValues'] = [
                        x if x['relatedLot'] == lot_id and (getattr(auction.bids[bid_index].lotValues[lotValue_index], 'status', 'active') or 'active') == 'active' else {}
                        for lotValue_index, x in enumerate(bid['lotValues'])
                    ]

    else:
        data = {}
    if request.method == 'POST':
        now = get_now().isoformat()
        if auction.lots:
            data['lots'] = [{'auctionPeriod': {'endDate': now}} if i.id == lot_id else {} for i in auction.lots]
        else:
            data['auctionPeriod'] = {'endDate': now}
    request.validated['data'] = data


def validate_bid_data(request, **kwargs):
    if not request.check_accreditation(request.auction.edit_accreditation):
        request.errors.add('procurementMethodType', 'accreditation', 'Broker Accreditation level does not permit bid creation')
        request.errors.status = 403
        raise error_handler(request)
    if request.auction.get('mode', None) is None and request.check_accreditation('t'):
        request.errors.add('procurementMethodType', 'mode', 'Broker Accreditation level does not permit bid creation')
        request.errors.status = 403
        raise error_handler(request)
    update_logging_context(request, {'bid_id': '__new__'})
    model = type(request.auction).bids.model_class
    return validate_data(request, model)

@raise_wrapper
def validate_patch_bid_data(request, **kwargs):
    model = type(request.auction).bids.model_class
    return validate_data(request, model, True)

@raise_wrapper
def validate_award_data(request, **kwargs):
    update_logging_context(request, {'award_id': '__new__'})
    model = type(request.auction).awards.model_class
    return validate_data(request, model)

@raise_wrapper
def validate_patch_award_data(request, **kwargs):
    model = type(request.auction).awards.model_class
    return validate_data(request, model, True)

@raise_wrapper
def validate_question_data(request, **kwargs):
    if not request.check_accreditation(request.auction.edit_accreditation):
        request.errors.add('procurementMethodType', 'accreditation', 'Broker Accreditation level does not permit question creation')
        request.errors.status = 403
        raise error_handler(request)
    if request.auction.get('mode', None) is None and request.check_accreditation('t'):
        request.errors.add('procurementMethodType', 'mode', 'Broker Accreditation level does not permit question creation')
        request.errors.status = 403
        raise error_handler(request)
    update_logging_context(request, {'question_id': '__new__'})
    model = type(request.auction).questions.model_class
    return validate_data(request, model)

@raise_wrapper
def validate_patch_question_data(request, **kwargs):
    model = type(request.auction).questions.model_class
    return validate_data(request, model, True)

@raise_wrapper
def validate_complaint_data(request, **kwargs):
    if not request.check_accreditation(request.auction.edit_accreditation):
        request.errors.add('procurementMethodType', 'accreditation', 'Broker Accreditation level does not permit complaint creation')
        request.errors.status = 403
        raise error_handler(request)
    if request.auction.get('mode', None) is None and request.check_accreditation('t'):
        request.errors.add('procurementMethodType', 'mode', 'Broker Accreditation level does not permit complaint creation')
        request.errors.status = 403
        raise error_handler(request)
    update_logging_context(request, {'complaint_id': '__new__'})
    model = type(request.auction).complaints.model_class
    return validate_data(request, model)

@raise_wrapper
def validate_patch_complaint_data(request, **kwargs):
    model = type(request.auction).complaints.model_class
    return validate_data(request, model, True)

@raise_wrapper
def validate_cancellation_data(request, **kwargs):
    update_logging_context(request, {'cancellation_id': '__new__'})
    model = type(request.auction).cancellations.model_class
    return validate_data(request, model)

@raise_wrapper
def validate_patch_cancellation_data(request, **kwargs):
    model = type(request.auction).cancellations.model_class
    return validate_data(request, model, True)

@raise_wrapper
def validate_contract_data(request, **kwargs):
    update_logging_context(request, {'contract_id': '__new__'})
    model = type(request.auction).contracts.model_class
    return validate_data(request, model)

@raise_wrapper
def validate_patch_contract_data(request, **kwargs):
    model = type(request.auction).contracts.model_class
    return validate_data(request, model, True)

@raise_wrapper
def validate_lot_data(request, **kwargs):
    update_logging_context(request, {'lot_id': '__new__'})
    model = type(request.auction).lots.model_class
    return validate_data(request, model)

@raise_wrapper
def validate_patch_lot_data(request, **kwargs):
    model = type(request.auction).lots.model_class
    return validate_data(request, model, True)
