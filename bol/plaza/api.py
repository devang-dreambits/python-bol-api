from __future__ import print_function

import time
import requests
import hmac
import hashlib
import base64
from datetime import datetime
import collections
from enum import Enum

import traceback


from xml.etree import ElementTree

from .models import Orders, Payments, Shipments, ProcessStatus

# custom Method Models For DreamBits
from .models import PurchasableShippingLabels, ReturnItems
from .models import OffersResponse, OfferFile  # DeleteBulkRequest

# for get Inventory method
from .models import InventoryResponse

# for Get All Bounds method
from .models import GetAllInbounds

# for Get Single Bounds method
from .models import GetSingleInbound


__all__ = ['PlazaAPI']

PLAZA_API_V1 = "https://plazaapi.bol.com/services/xsd/v1/plazaapi.xsd"
# NS_MAP = {None:PLAZA_API_V1}
NS_MAP = {"":PLAZA_API_V1}

class TransporterCode(Enum):
    """
    https://developers.bol.com/documentatie/plaza-api/developer-guide-plaza-api/appendix-a-transporters/
    """
    DHLFORYOU = 'DHLFORYOU'
    UPS = 'UPS'
    KIALA_BE = 'KIALA-BE'
    KIALA_NL = 'KIALA-NL'
    TNT = 'TNT'
    TNT_EXTRA = 'TNT-EXTRA'
    TNT_BRIEF = 'TNT_BRIEF'
    TNT_EXPRESS = 'TNT-EXPRESS'
    SLV = 'SLV'
    DYL = 'DYL'
    DPD_NL = 'DPD-NL'
    DPD_BE = 'DPD-BE'
    BPOST_BE = 'BPOST_BE'
    BPOST_BRIEF = 'BPOST_BRIEF'
    BRIEFPOST = 'BRIEFPOST'
    GLS = 'GLS'
    FEDEX_NL = 'FEDEX_NL'
    FEDEX_BE = 'FEDEX_BE'
    OTHER = 'OTHER'
    DHL = 'DHL'
    DHL_DE = 'DHL_DE'
    DHL_GLOBAL_MAIL = 'DHL-GLOBAL-MAIL'
    TSN = 'TSN'
    FIEGE = 'FIEGE'
    TRANSMISSION = 'TRANSMISSION'
    PARCEL_NL = 'PARCEL-NL'
    LOGOIX = 'LOGOIX'
    PACKS = 'PACKS'

    @classmethod
    def to_string(cls, transporter_code):
        if isinstance(transporter_code, TransporterCode):
            transporter_code = transporter_code.value
        assert transporter_code in map(
            lambda c: c.value, list(TransporterCode))
        return transporter_code


class MethodGroup(object):

    def __init__(self, api, group):
        self.api = api
        self.group = group

    def request(self, method, path='', params={}, data=None,
                accept="application/xml"):
        uri = '/services/rest/{group}/{version}{path}'.format(
            group=self.group,
            version=self.api.version,
            path=path)
        xml = self.api.request(method, uri, params=params, data=data,
                               accept=accept)
        return xml

    def request_inbound(self, method, path='', params={}, data=None,
                        accept="application/xml"):
        uri = '/services/rest/{group}/{path}'.format(
            group=self.group,
            path=path)
        xml = self.api.request(method, uri, params=params, data=data,
                               accept=accept)
        return xml

    def create_request_xml(self, root, **kwargs):
        elements = self._create_request_xml_elements(1, **kwargs)
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<{root} xmlns="https://plazaapi.bol.com/services/xsd/v2/plazaapi.xsd">
{elements}
</{root}>
""".format(root=root, elements=elements)
        return xml

    def create_request_offers_xml(self, root, **kwargs):
        elements = self._create_request_xml_elements(1, **kwargs)
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<{root} xmlns="https://plazaapi.bol.com/offers/xsd/api-2.0.xsd">
{elements}
</{root}>
""".format(root=root, elements=elements)
        return xml

    def create_request_inbound_xml(self, root, **kwargs):
        elements = self._create_request_xml_elements(1, **kwargs)
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<{root} xmlns="https://plazaapi.bol.com/services/xsd/v1/plazaapi.xsd">
{elements}
</{root}>
""".format(root=root, elements=elements)
        return xml

    def _create_request_xml_elements(self, indent, **kwargs):
        # sort to make output deterministic
        kwargs = collections.OrderedDict(sorted(kwargs.items()))
        xml = ''
        for tag, value in kwargs.items():
            if value is not None:
                prefix = ' ' * 4 * indent
                if not isinstance(value, list):
                    if isinstance(value, dict):
                        text = '\n{}\n{}'.format(
                            self._create_request_xml_elements(
                                indent + 1, **value),
                            prefix)
                    elif isinstance(value, datetime):
                        text = value.isoformat()
                    else:
                        text = str(value)
                    # TODO: Escape! For now this will do I am only dealing
                    # with track & trace codes and simplistic IDs...
                    if xml:
                        xml += '\n'
                    xml += prefix
                    xml += "<{tag}>{text}</{tag}>".format(
                        tag=tag,
                        text=text
                    )
                else:
                    for item in value:
                        if isinstance(item, dict):
                            text = '\n{}\n{}'.format(
                                self._create_request_xml_elements(
                                    indent + 1, **item),
                                prefix)
                        else:
                            text = str(item)
                        # TODO: Escape! For now this will do I am only dealing
                        # with track & trace codes and simplistic IDs...
                        if xml:
                            xml += '\n'
                        xml += prefix
                        xml += "<{tag}>{text}</{tag}>".format(
                            tag=tag,
                            text=text
                        )
        return xml


class OrderMethods(MethodGroup):

    def __init__(self, api):
        super(OrderMethods, self).__init__(api, 'orders')

    def list(self):
        xml = self.request('GET')
        return Orders.parse(self.api, xml)


class PaymentMethods(MethodGroup):

    def __init__(self, api):
        super(PaymentMethods, self).__init__(api, 'payments')

    def list(self, year, month):
        xml = self.request('GET', '/%d%02d' % (year, month))
        return Payments.parse(self.api, xml)


class ProcessStatusMethods(MethodGroup):

    def __init__(self, api):
        super(ProcessStatusMethods, self).__init__(api, 'process-status')

    def get(self, id):
        xml = self.request('GET', '/{}'.format(id))
        return ProcessStatus.parse(self.api, xml)


class ShipmentMethods(MethodGroup):

    def __init__(self, api):
        super(ShipmentMethods, self).__init__(api, 'shipments')

    def list(self, page=None):
        if page is not None:
            params = {'page': page}
        else:
            params = None
        xml = self.request('GET', params=params)
        return Shipments.parse(self.api, xml)

    def create(self, order_item_id, date_time, expected_delivery_date,
               shipment_reference=None, transporter_code=None,
               track_and_trace=None, shipping_label_code=None):
        # Moved the params to a dict so it can be easy to add/remove parameters
        values = {
            'OrderItemId': order_item_id,
            'DateTime': date_time,
            'ShipmentReference': shipment_reference,
            'ExpectedDeliveryDate': expected_delivery_date,
        }

        if transporter_code:
            transporter_code = TransporterCode.to_string(
                transporter_code)

        if shipping_label_code:
            values['ShippingLabelCode'] = shipping_label_code
        else:
            values['Transport'] = {
                'TransporterCode': transporter_code,
                'TrackAndTrace': track_and_trace
            }

        xml = self.create_request_xml(
            'ShipmentRequest',
            **values)

        response = self.request('POST', data=xml)
        return ProcessStatus.parse(self.api, response)


class TransportMethods(MethodGroup):

    def __init__(self, api):
        super(TransportMethods, self).__init__(api, 'transports')

    def update(self, id, transporter_code, track_and_trace):
        transporter_code = TransporterCode.to_string(transporter_code)
        xml = self.create_request_xml(
            'ChangeTransportRequest',
            TransporterCode=transporter_code,
            TrackAndTrace=track_and_trace)
        response = self.request('PUT', '/{}'.format(id), data=xml)
        return ProcessStatus.parse(self.api, response)

    def getSingle(self, transportId, shippingLabelId, file_location):
        content = self.request('GET', '/{}/shipping-label/{}'.format(
            transportId,
            shippingLabelId),
            params={}, data=None, accept="application/pdf")
        # Now lets store this content in pdf:

        with open(file_location, 'wb') as f:
            f.write(content)


class PurchasableShippingLabelsMethods(MethodGroup):

    def __init__(self, api):
        super(PurchasableShippingLabelsMethods, self).__init__(
            api,
            'purchasable-shipping-labels')

    def get(self, id):
        params = {'orderItemId': id}
        xml = self.request('GET', params=params)
        return PurchasableShippingLabels.parse(self.api, xml)


class ReturnItemsMethods(MethodGroup):

    def __init__(self, api):
        super(ReturnItemsMethods, self).__init__(api, 'return-items')

    def getUnhandled(self):
        xml = self.request('GET', path="/unhandled", accept="application/xml")
        return ReturnItems.parse(self.api, xml)

    def getHandle(self, orderId, status_reason, qty_return):
        xml = self.request('PUT', '/{}/handle'.format(orderId), params={
            'StatusReason': status_reason,
            'QuantityReturned': qty_return
        })
        return ProcessStatus.parse(self.api, xml)


class OffersMethods(MethodGroup):

    def __init__(self, api):
        super(OffersMethods, self).__init__(api, 'offers')

    def upsertOffers(self, offers, path='/', params={},
                     data=None, accept="application/xml"):
        xml = self.create_request_offers_xml(
            'UpsertRequest',
            RetailerOffer=offers)
        uri = '/{group}/{version}{path}'.format(
            group=self.group,
            version=self.api.version,
            path=path)
        response = self.api.request('PUT', uri, params=params,
                                    data=xml, accept=accept)
        # return ProcessStatus.parse(self.api, xml)
        if response is True:
            return response
        # else:
        #     return UpsertOffersError.parse(self.api, response)

    def getSingleOffer(self, ean, path='/', params={},
                       data=None, accept="application/xml"):

        uri = '/{group}/{version}{path}'.format(
            group=self.group,
            version=self.api.version,
            path='/{}'.format(ean))
        response = self.api.request('GET', uri, params=params,
                                    data=data, accept=accept)
        return OffersResponse.parse(self.api, response)

    def getOffersFileName(self, path='/', params={},
                          data=None, accept="application/xml"):

        uri = '/{group}/{version}{path}'.format(
            group=self.group,
            version=self.api.version,
            path='/export/')
        response = self.api.request('GET', uri, params=params,
                                    data=data, accept=accept)
        return OfferFile.parse(self.api, response)

    def getOffersFile(self, csv, path='/', params={},
                      data=None, accept="text/csv"):
        csv_path = csv.split("/v2/")
        uri = '/{group}/{version}{path}'.format(
            group=self.group,
            version=self.api.version,
            path='/{}'.format(csv_path[1]))
        response = self.api.request('GET', uri, params=params,
                                    data=data, accept=accept)
        return response

    def deleteOffers(self, offers, path='/', params={},
                     data=None, accept="application/xml"):
        try:
            xml = self.create_request_offers_xml(
                'DeleteBulkRequest',
                RetailerOfferIdentifier=offers[0])
            uri = '/{group}/{version}{path}'.format(
                group=self.group,
                version=self.api.version,
                path=path)
            response = self.api.request("DELETE", uri, params=params,
                                        data=xml, accept=accept)
            if response is True:
                return response
        except Exception:
            print("Got into Exception \n{0}".format(traceback.print_exc()))


class InboundMethods(MethodGroup):

    def __init__(self, api):
        super(InboundMethods, self).__init__(api, 'inbounds')

    def getAllInbounds(self, page=None):
        uri = '/services/rest/{group}'.format(
            group=self.group)
        # all_inbound = self.api.request('GET', uri)

        all_inbound_rspn = """<?xml version="1.0" encoding="UTF-8"
standalone="yes"?>
<Inbounds xmlns="https://plazaapi.bol.com/services/xsd/v1/plazaapi.xsd">
  <TotalCount>4</TotalCount>
  <TotalPageCount>1</TotalPageCount>
      <Inbound>
        <Id>1124284930</Id>
        <Reference>FBB20170726</Reference>
        <CreationDate>2017-07-26T10:58:17.079+02:00</CreationDate>
        <State>ArrivedAtWH</State>
        <LabellingService>false</LabellingService>
        <AnnouncedBSKUs>69</AnnouncedBSKUs>
        <AnnouncedQuantity>237</AnnouncedQuantity>
        <ReceivedBSKUs>69</ReceivedBSKUs>
        <ReceivedQuantity>240</ReceivedQuantity>
        <TimeSlot>
          <Start>2017-07-28T06:00:00.000+02:00</Start>
          <End>2017-07-28T19:00:00.000+02:00</End>
        </TimeSlot>
        <FbbTransporter>
          <Name>PostNL</Name>
          <Code>PostNL</Code>
        </FbbTransporter>
      </Inbound>
      <Inbound>
        <Id>1124284929</Id>
        <Reference>FBB20170712</Reference>
        <CreationDate>2017-07-12T21:08:02.433+02:00</CreationDate>
        <State>ArrivedAtWH</State>
        <LabellingService>false</LabellingService>
        <AnnouncedBSKUs>85</AnnouncedBSKUs>
        <AnnouncedQuantity>204</AnnouncedQuantity>
        <ReceivedBSKUs>90</ReceivedBSKUs>
        <ReceivedQuantity>203</ReceivedQuantity>
        <TimeSlot>
          <Start>2017-07-17T06:00:00.000+02:00</Start>
          <End>2017-07-17T19:00:00.000+02:00</End>
        </TimeSlot>
        <FbbTransporter>
          <Name>PostNL</Name>
          <Code>PostNL</Code>
        </FbbTransporter>
      </Inbound>
</Inbounds>"""
        print("all_inbound_rsp-> {0}".format(all_inbound_rspn))
        all_inbound = ElementTree.fromstring(all_inbound_rspn)
        print("all_inbound-> {0}".format(all_inbound))

        # need to handle the structure after modifying xml data
        # as the data is not structured properly

        ElementTree.register_namespace("", PLAZA_API_V1)

        print("all_inbound_rsp-> {0}".format(all_inbound_rspn))
        all_inbound = ElementTree.fromstring(all_inbound_rspn)
        print("all_inbound-> {0}".format(all_inbound))

        print("all_inbound-> {0}".format(all_inbound))
        print("dir(all_inbound) -> {0}".format(dir(all_inbound)))
        print('all_inbound.find("Inbound")-> {0}'.format(all_inbound.find("Inbound")))
        print('all_inbound.findall("Inbound")-> {0}'.format(all_inbound.findall("Inbound")))
        allit = list(all_inbound)
        print("allit-> {0}".format(allit))
        #for x in allit:
        #    print x
        #    print x.tag

        inbounds = [x for x in all_inbound.iter()
                        if x.tag.partition('}')[2]=="Inbound"]

        print("inbounds-> {0}".format(inbounds))
        print("all_inbound.iter()-> {0}".format(all_inbound.iter()))
        for x in inbounds:
            all_inbound.remove(x)

        print("list(all_inbound)-> {0}".format(list(all_inbound)))

        newinbound = ElementTree.Element('AllInbound', nsmap=PLAZA_API_V1)
        # newinbound = ElementTree.Qname(PLAZA_API_V1, tag='AllInbound')
        for x in inbounds:
            newinbound.append(x)

        print("newinbound-> {0}".format(newinbound))

        all_inbound.append(newinbound)

        print("list(all_inbound)-> {0}".format(list(all_inbound)))
        print("ElementTree.tostring(all_inbound)-> {0}".format(ElementTree.tostring(all_inbound)))

        # for x in inbounds:
        #     newinbound.append(x)
        # all_inbound.append(newinbound)
        # print("list(all_inbound) -> {0}".format(list(all_inbound)))

        return GetAllInbounds.parse(self.api, all_inbound)

    def getSingleInbound(self, inbound_id=None):
        response = self.request_inbound('GET', path=inbound_id)
        return GetSingleInbound.parse(self.api, response)

    def create(self, reference=None, time_slot=None, fbb_code=None,
               fbb_name=None, labelling_service=None, prod_ean=None,
               prod_annc_qty=None):
        # Moved the params to a dict so it can be easy to add/remove parameters
        values = {
            'Reference': reference,
            'LabellingService': labelling_service
        }

        if fbb_code:
            if 'FbbTransporter' not in values:
                values['FbbTransporter'] = {}
            values['FbbTransporter']['Code'] = fbb_code

        if fbb_name:
            if 'FbbTransporter' not in values:
                values['FbbTransporter'] = {}
            values['FbbTransporter']['Name'] = fbb_name

        if prod_ean:
            if 'Products' not in values:
                values['Products'] = {'Product': {}}
            values['Products']['Product']['EAN'] = prod_ean
        if prod_annc_qty:
            if 'Products' not in values:
                values['Products'] = {'Product': {}}
            values['Products']['Product']['AnnouncedQuantity'] = prod_annc_qty

        xml = self.create_request_inbound_xml(
            'InboundRequest',
            **values)

        response = self.request('POST', data=xml)
        return ProcessStatus.parse(self.api, response)


class InventoryMethods(MethodGroup):

    def __init__(self, api):
        super(InventoryMethods, self).__init__(api, 'inventory')

    def getInventory(self, page=None, quantity=None, stock=None, state=None,
                     query=None):
        params = {}

        if page:
            params['page'] = page

        if quantity:
            params['quantity'] = quantity

        if stock:
            params['stock'] = stock

        if state:
            params['state'] = state

        if query:
            params['query'] = query

        # xml = self.request('GET', params=params)

        uri = '/services/rest/{group}'.format(group=self.group)
        response = self.api.request('GET', uri, params=params,
                                    data=None)
        return InventoryResponse.parse(self.api, response)


class PlazaAPI(object):

    def __init__(self, public_key, private_key, test=False, timeout=None,
                 session=None):

        self.public_key = public_key
        self.private_key = private_key
        self.url = 'https://%splazaapi.bol.com' % ('test-' if test else '')

        self.version = 'v2'
        self.timeout = timeout
        self.orders = OrderMethods(self)
        self.payments = PaymentMethods(self)
        self.shipments = ShipmentMethods(self)
        self.process_status = ProcessStatusMethods(self)
        self.transports = TransportMethods(self)
        self.labels = PurchasableShippingLabelsMethods(self)
        self.session = session or requests.Session()
        self.return_items = ReturnItemsMethods(self)
        self.offers = OffersMethods(self)
        self.inbounds = InboundMethods(self)
        self.inventory = InventoryMethods(self)

    def request(self, method, uri, params={},
                data=None, accept="application/xml"):
        try:
            content_type = 'application/xml; charset=UTF-8'
            date = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
            msg = """{method}

{content_type}
{date}
x-bol-date:{date}
{uri}""".format(content_type=content_type,
                date=date,
                method=method,
                uri=uri)
            h = hmac.new(
                self.private_key.encode('utf-8'),
                msg.encode('utf-8'), hashlib.sha256)
            b64 = base64.b64encode(h.digest())

            signature = self.public_key.encode('utf-8') + b':' + b64

            headers = {'Content-Type': content_type,
                       'X-BOL-Date': date,
                       'X-BOL-Authorization': signature,
                       'accept': accept}

            request_kwargs = {
                'method': method,
                'url': self.url + uri,
                'params': params,
                'headers': headers,
                'timeout': self.timeout,
            }
            if data:
                request_kwargs['data'] = data

            resp = self.session.request(**request_kwargs)

            if request_kwargs['url'] == 'https://plazaapi.bol.com/offers/v2/':
                if resp.status_code == 202 and resp.text is not None:
                    return True
                else:
                    tree = ElementTree.fromstring(resp.content)
                    return tree

            if 'https://plazaapi.bol.com/offers/v2/export/' in request_kwargs[
                    'url']:
                if accept == "text/csv":
                    return resp.text

            resp.raise_for_status()

            if accept == "application/pdf":
                return resp.content
            else:
                tree = ElementTree.fromstring(resp.content)
                return tree
        except Exception:
            print("Got into Exception \n{0}".format(traceback.print_exc()))
            return False
