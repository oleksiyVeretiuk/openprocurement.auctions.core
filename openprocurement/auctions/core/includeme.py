# -*- coding: utf-8 -*-
import logging
import os

from pyramid.events import ContextFound
from pyramid.interfaces import IRequest

from openprocurement.api.interfaces import (
    IContentConfigurator,
    IAwardingNextCheck
)
from openprocurement.api.utils import get_content_configurator, configure_plugins

from openprocurement.auctions.core.adapters import (
    AuctionConfigurator,
    AuctionAwardingNextCheckAdapter
)
from openprocurement.auctions.core.design import add_design
from openprocurement.auctions.core.models import IAuction
from openprocurement.auctions.core.utils import (
    set_logging_context,
    extract_auction,
    register_auction_procurementMethodType,
    isAuction,
    auction_from_data,
    init_plugins,
    awardingTypePredicate
)

LOGGER = logging.getLogger(__name__)


def includeme(config, plugin_config=None):
    add_design()
    config.add_subscriber(set_logging_context, ContextFound)

    # auction procurementMethodType plugins support
    config.registry.auction_procurementMethodTypes = {}
    config.registry.pmtConfigurator = {}
    config.add_route_predicate('auctionsprocurementMethodType', isAuction)
    config.add_route_predicate('awardingType', awardingTypePredicate)
    config.add_request_method(extract_auction, 'auction', reify=True)
    config.add_request_method(auction_from_data)
    config.add_directive(
        'add_auction_procurementMethodType',
        register_auction_procurementMethodType
    )
    config.scan("openprocurement.auctions.core.views")
    config.scan("openprocurement.api.subscribers")
    init_plugins(config)

    # register Adapters
    config.registry.registerAdapter(
        AuctionConfigurator,
        (IAuction, IRequest),
        IContentConfigurator
    )
    config.registry.registerAdapter(
        AuctionAwardingNextCheckAdapter,
        (IAuction, ),
        IAwardingNextCheck
    )

    config.add_request_method(get_content_configurator, 'content_configurator', reify=True)

    LOGGER.info("Included openprocurement.auctions.core plugin", extra={'MESSAGE_ID': 'included_plugin'})

    if plugin_config and plugin_config.get('plugins'):
        for name in plugin_config['plugins']:
            package_config = plugin_config['plugins'][name]
            configure_plugins(
                config, {name: package_config}, 'openprocurement.auctions.core.plugins', name
            )
            # migrate data
            if package_config.get('migration') and not os.environ.get('MIGRATION_SKIP'):
                configure_plugins(
                    config.registry, {name: None}, 'openprocurement.api.migrations', name
                )
