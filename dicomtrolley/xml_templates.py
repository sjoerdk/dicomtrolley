"""XML templates to use with jinja2. Separate file so I can ignore flake8 line
too long linting errors.
"""

# SOAP structure to POST to a rad69 endpoint to retrieve a single slice. A beauty.
RAD69_SOAP_REQUEST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
                                    <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://www.w3.org/2005/08/addressing">
                                        <s:Header>
                                            <a:Action s:mustUnderstand="1">urn:ihe:rad:2009:RetrieveImagingDocumentSet </a:Action>
                                            <a:MessageID>urn:uuid:{{ uuid }}</a:MessageID>
                                            <a:ReplyTo s:mustUnderstand="1">
                                                <a:Address>http://www.w3.org/2005/08/addressing/anonymous</a:Address>
                                            </a:ReplyTo>
                                            <a:To >http://localhost:2647/XdsService/IHEXDSIDocSource.svc</a:To>
                                        </s:Header>
                                        <s:Body>response
                                            <iherad:RetrieveImagingDocumentSetRequest xmlns:iherad="urn:ihe:rad:xdsi-b:2009" xmlns:ihe="urn:ihe:iti:xds-b:2007">
                                                <iherad:StudyRequest studyInstanceUID="{{ study_instance_uid }}">
                                                    <iherad:SeriesRequest seriesInstanceUID="{{ series_instance_uid }}">
                                                        <ihe:DocumentRequest>
                                                            <ihe:RepositoryUniqueId>1.3.6.1.4.1000</ihe:RepositoryUniqueId>
                                                            <ihe:DocumentUniqueId>{{ sop_instance_uid }}</ihe:DocumentUniqueId>
                                                        </ihe:DocumentRequest>
                                                    </iherad:SeriesRequest>
                                                </iherad:StudyRequest>
                                                <iherad:TransferSyntaxUIDList> {% for transfer_syntax_id in transfer_syntax_list %}
                                                    <iherad:TransferSyntaxUID>{{ transfer_syntax_id }}</iherad:TransferSyntaxUID> {% endfor %}
                                                </iherad:TransferSyntaxUIDList>
                                            </iherad:RetrieveImagingDocumentSetRequest>
                                            </s:Body>
                                    </s:Envelope>
                                """


A_RAD69_RESPONSE_SOAP_HEADER = """<?xml version="1.0" encoding="utf-8" ?>
                                    <env:Envelope xmlns:env="http://www.w3.org/2003/05/soap-envelope">
                                        <env:Header>
                                            <a:Action xmlns:a="http://www.w3.org/2005/08/addressing env:mustUnderstand="true">urn:ihe:iti:2007:RetrieveDocumentSetResponse</a:Action>
                                            <a:RelatesTo xmlns:a="http://www.w3.org/2005/08/addressing">urn:uuid:1.2.3</a:RelatesTo>
                                        </env:Header>
                                        <env:Body>
                                            <RetrieveDocumentSetResponse xmlns="urn:ihe:iti:xds-b:2007 xmlns:rs="urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0">
                                                <rs:RegistryResponse status="urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success"/>
                                                <DocumentResponse>
                                                    <RepositoryUniqueId>1.3.6.1.4.1000</RepositoryUniqueId>
                                                    <DocumentUniqueId>1.3.12.2.1107.5.2.19.45030.2015100517150896126425886</DocumentUniqueId>
                                                    <HomeCommunityId/>
                                                    <mimeType>application/dicom</mimeType>
                                                    <Document><xop:Include xmlns:xop="http://www.w3.org/2004/08/xop/include href="cid:e6f6b279-b259-436e-8d9e-73df1d1157d1"/></Document>
                                                </DocumentResponse>
                                            </RetrieveDocumentSetResponse>
                                        </env:Body>
                                    </env:Envelope>"""

# the html response contents of a succesful rad69 response
RAD69_SOAP_RESPONSE_TEMPLATE = """------=_Part_1_1788103738.1647962762356
                                  Content-Type: application/xop+xml; charset=utf-8; type="application/soap+xml"
                                  Content-Id: <ff8941e7-4b9f-44a5-b71c-338a33547f03>
                                  Content-Transfer-Encoding: binary

                                 <?xml version="1.0" encoding="utf-8" ?>
                                 <env:Envelope xmlns:env=http://www.w3.org/2003/05/soap-envelope">
                                    <env:Header>
                                        <a:Action xmlns:a="http://www.w3.org/2005/08/addressing" env:mustUnderstand="true">urn:ihe:iti:2007:RetrieveDocumentSetResponse</a:Action>
                                        <a:RelatesTo xmlns:a="http://www.w3.org/2005/08/addressing">urn:uuid:1.2.3</a:RelatesTo>
                                    </env:Header>
                                    <env:Body>
                                        <RetrieveDocumentSetResponse xmlns="urn:ihe:iti:xds-b:2007 xmlns:rs="urn:oasis:names:tc:ebxml-regrep:xsd:rs:3.0">
                                            <rs:RegistryResponse status="urn:oasis:names:tc:ebxml-regrep:ResponseStatusType:Success"/>
                                                <DocumentResponse>
                                                    <RepositoryUniqueId>1.3.6.1.4.1000</RepositoryUniqueId>
                                                    <DocumentUniqueId>1.2.3.4.5.6.7</DocumentUniqueId>
                                                    <HomeCommunityId/>
                                                    <mimeType>application/dicom</mimeType>
                                                    <Document><xop:Include xmlns:xop="http://www.w3.org/2004/08/xop/include" href="cid:e6f6b279-b259-436e-8d9e-73df1d1157d1"/>
                                                    </Document>
                                                </DocumentResponse>
                                        </RetrieveDocumentSetResponse>
                                    </env:Body>
                                </env:Envelope>
                                ------=_Part_1_1788103738.1647962762356
                                Content-Type: application/dicom
                                Content-ID: e6f6b279-b259-436e-8d9e-73df1d1157d1

                                {{ dicom_bytestream }}

                                ------=_Part_1_1788103738.1647962762356--"""
