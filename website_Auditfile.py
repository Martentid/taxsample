# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 11:34:20 2020

@author: marte
"""
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 29 15:47:16 2020

@author: marte
"""
import numpy as np
from PIL import Image
import xml.etree.ElementTree as ET
import streamlit as st
import pandas as pd
import base64
taxsample = Image.open('TaxSample-logo.png')

st.set_option('deprecation.showfileUploaderEncoding', False)


def parse_info(root,ns): # Bedoeld om alle informatie uit de root van de auditfile te halen. Er moet ook een manier zijn om in dit 1 functie te kunnen schrijven, maar voor nu werkt dit ook.
   
    recordcontent = dict()
    
    for child in root:
        columnname = child.tag.replace(ns,'')
        columnvalue = child.text
        
        if len(child) == 0:
            recordcontent[columnname] = columnvalue     
            
        else: continue
            
    return recordcontent  

def stamtabellen(root,ns) :    # bedoeld om subtabellen als customer supplier uit te lezen.
    
    currentrow = 0
    records = dict()

    for child in root:

        module = child.tag.replace(ns,'')
        recordcontent = dict()

        for subchild in child:

            if len(subchild) != 0:
                for subsubchild in subchild:
                    columnvalue = subsubchild.text
                    columnname = subsubchild.tag.replace(ns,'')
                    recordcontent[columnname] = columnvalue

                    if len(subsubchild) != 0: print('let op! nog een sublaag gevonden')
            else:
                columnvalue =subchild.text
                columnname = subchild.tag.replace(ns,'')
                recordcontent[columnname] = columnvalue

        records[currentrow] = recordcontent
        currentrow +=1

    df = pd.DataFrame(records).transpose()
    return df

def tags_in_module(modules,ns): # functie om de tags van de xmllaag uit te lezen. Dit zijn soms namen van submodules maar kunnen ook kolomnamen zijn.
    tag = dict()
    
    for submodule in modules:
        tagname = submodule.tag.replace(ns,'')
        tag[tagname] = tag.get(tagname, 0) + 1
    return tag

def accounttype(dataframe): # functie voor het bepalen van categorie Balans of Winst & Verlies

    conditions = [
        (dataframe['accTp'] == 'P'),
        (dataframe['accTp'] == 'B')]

    choices = ['Winst & verlies','Balans']

    dataframe['accounttype'] = np.select(conditions, choices, default= 'onbekende balanstype' + dataframe['accTp'] )

def journaltype(dataframe): # functie voor het bepalen van de dagboektypes.

    conditions = [
        (dataframe['jrnTp'] == 'Z'),
        (dataframe['jrnTp'] == 'B'),
        (dataframe['jrnTp'] == 'P'),
        (dataframe['jrnTp'] == 'O'),
        (dataframe['jrnTp'] == 'C'),
        (dataframe['jrnTp'] == 'M'),
        (dataframe['jrnTp'] == 'Y'),
        (dataframe['jrnTp'] == 'S')]

    choices = ['memoriaal', 'bankboek' , 'inkoopboek' , 'open/sluit balans', 'kasboek', 'memoriaal', 'salaris', 'verkoopboek']

    dataframe['journaltype'] = np.select(conditions, choices, default= 'onbekend dagboek' )
    
def vat_amount(dataframe): # functie die de waarde van kolom vat_amount in het goede formaat staat. de kolom wordt hernoemt naar vat_amount

    vat_amount_raw = dataframe['vatAmnt'].astype(float)
    
    conditions = [
        (dataframe['vatAmntTp'] == 'C'),
        (dataframe['vatAmntTp'] == 'D')]

    choices = [-1,1]

    dataframe['vat_amount'] = np.select(conditions, choices, default= 1 ) * vat_amount_raw

def amount(dataframe): # functie die de waarde van kolom amount in het goede formaat staat. de kolom wordt hernoemt naar amount



    amount_raw = dataframe['amnt'].astype(float)
    
    conditions = [
        (dataframe['amntTp'] == 'C'),
        (dataframe['amntTp'] == 'D')]

    choices = [-1,1]

    dataframe['amount'] = np.select(conditions, choices, default= 1 ) * amount_raw

# Lees Metadata
def lees_metadata(root,file ):
    namespaces = {'xsd':"http://www.w3.org/2001/XMLSchema", 'xsi':"http://www.w3.org/2001/XMLSchema-instance" }
    ns_raw =  root.tag.split('{')[1].split('}')[0]
    ns = '{'+ ns_raw + '}'
    namespaces['af'] = ns_raw
    header    = root.find('af:header',namespaces) # zoekt in de xml naar de tag header
    company   = root.find('af:company', namespaces) # zoekt in de xml naar de tag company
    transactions = root.find('af:company/af:transactions', namespaces) # zoekt in de xml naar de tag company/transactions (rekening houdend met de prefix van de namespaces)

    # zoek per laag naar de informatie die uniek is voor de auditfile.
    headerinfo = pd.DataFrame(parse_info(header,ns), index = [0])
    companyinfo = pd.DataFrame(parse_info(company, ns), index = [0])
    transactioninfo = pd.DataFrame(parse_info(transactions,ns), index = [0])

    # plak al deze informatie over de metadata van de auditfiles in 1 dataframe. Dit past in 1 regel.

    af_info = pd.concat([headerinfo, companyinfo, transactioninfo], axis = 1)

    af_info['file'] = file
    return af_info,namespaces,ns,ns_raw, company, header, transactions

# Lees stamtabellen uit 
def lees_stamtabellen(namespaces, ns, company):
    periods = stamtabellen(company.findall('af:periods/af:period',namespaces),ns)
    custsup = stamtabellen(company.findall('af:customersSuppliers/af:customerSupplier',namespaces),ns)
    vatcode = stamtabellen(company.findall('af:vatCodes/af:vatCode',namespaces),ns)
    genledg  = stamtabellen(company.findall('af:generalLedger/af:ledgerAccount',namespaces),ns)
    basics  = stamtabellen(company.findall('af:generalLedger/af:basics',namespaces),ns)
    openingsubBalance = stamtabellen(company.findall('af:openingBalance/af:obSubledgers/af:obSubledger/af:obSbLine',namespaces),ns)
    openingBalance = stamtabellen(company.findall('af:openingBalance/af:obLine',namespaces),ns)
    subledger = stamtabellen(company.findall('af:transactions/af:subledgers/af:subledger/af:sbLine',namespaces),ns)
    
    # ontdubbel vat ID's die een claim en pay account hebben. deze kunnen later voor een verdubbeling van de data leiden.
    # wel nemen we alle informatie mee door de twee tabellen te splitsen en vervolgens op vatID aan elkaar te joinen.
    
    if vatcode.empty is False:
        try:
            claim = vatcode[(['vatID', 'vatDesc','vatToClaimAccID'])]
        except: 
            pass
        claim = claim[pd.isnull(claim['vatToClaimAccID']) == False]
    
        pay = vatcode[(['vatID', 'vatDesc','vatToPayAccID'])]
        pay = pay[pd.isnull(pay['vatToPayAccID']) == False]
    
        vatcode = pd.merge(claim,pay, on = ['vatID', 'vatDesc'], how ='outer')
    return periods, custsup,vatcode,genledg,basics, openingsubBalance, openingBalance, subledger

# lees journaal deabase uit
def lees_journal(namespaces, ns, company):
    journals = company.findall('af:transactions/af:journal', namespaces)
    journal_df = pd.DataFrame()

    for journal in journals: # importeert de aanwezig dagboeken. Per dagboek zijn de transacties in een sublaag te vinden.
        jrninfo = dict()

        for records in journal:
            if len(records) == 0:
                columnnames = records.tag.replace(ns,'')
                columnvalues = records.text
                jrninfo[columnnames] = columnvalues
        journal_df = journal_df.append(jrninfo, ignore_index = True)


    journaltype(journal_df) # format het juiste dagboektype
    journal_df = journal_df.drop(['jrnTp'] , axis = 1)
    return journal_df,journals

# lees de transacties datbase uit
def lees_trans(ns,journals):
    transactions_df = pd.DataFrame()

    total_records = list()
    record_dict = dict()

    for journal in journals: # voor alle dagboeken in de auditfile


        for records in journal: # voor de alle records die in het dagboek zitten

            if len(records) == 0:
                columnnames = records.tag.replace(ns,'')
                columnvalues = records.text
                record_dict[columnnames] = columnvalues

            else:
                for record in records: # voor alle velden in de record
                    if len(record) == 0:
                        columnnames = record.tag.replace(ns,'')
                        columnvalues = record.text
                        record_dict[columnnames] = columnvalues # de kolomnaam en kolomwaarde van dit record

                    else:

                        for subfields in record: # soms zit de informatie nog een laag dieper.
                            if len(subfields) == 0:
                                columnnames = subfields.tag.replace(ns,'')
                                columnvalues = subfields.text
                                record_dict[columnnames] = columnvalues #  de kolomnaam en kolomwaarde van dit record

                            else: 

                                for subfields_1 in subfields: # check of er nog een laag dieper is. als dit zo is krijg je terug dat er nog een sublaag is gevonden. Normaliter zal deze if statement nooit getriggered worden.
                                    if len(subfields_1) == 0:
                                        columnnames = subfields_1.tag.replace(ns,'')
                                        columnvalues = subfields_1.text
                                        record_dict[columnnames] = columnvalues
                                    else : print('nog een sublaag!')


                        total_records.append(record_dict.copy()) # plak de record aan de totaal tabel.
                        record_dict.pop('vatID',None)
                        record_dict.pop('projID',None)
                        record_dict.pop('vatPerc',None)
                        record_dict.pop('custSupID',None)
                        record_dict.pop('invRef',None)
                        record_dict.pop('bankAccNr',None)
                        record_dict.pop('amount',None)
                        record_dict.pop('vat_amount',None)
                        
    transactions_df = transactions_df.append(total_records, ignore_index = True)
    tr = transactions_df 

    amount(tr) # zet het amountveld in het juiste formaat --> zie functies

    tr = tr.drop(['amnt', 'amntTp', ], axis=1)


    tr['effDate'] = pd.to_datetime(tr['effDate'])
    tr['trDt'] = pd.to_datetime(tr['trDt'])

    if 'vatAmnt' in tr.columns:
        vat_amount(tr)  # zet het vat_amount veld in het juiste formaat --> zie functies
        tr = tr.drop(['vatAmnt', 'vatAmntTp'], axis=1)

    else:
        print('geen vat amount!')
        tr['vatID'] = None
    return tr

def get_df_name(df):
    name =[x for x in globals() if globals()[x] is df][0]
    return name

def add_column(i):
    af_info['Bestandscode']=i
    tr['Bestandscode']=i
    journal_df['Bestandscode']=i
    basics['Bestandscode']=i
    genledg['Bestandscode']=i
    vatcode['Bestandscode']=i
    periods['Bestandscode']=i
    custsup['Bestandscode']=i
    openingsubBalance['Bestandscode']=i
    openingBalance['Bestandscode']=i
    subledger['Bestandscode']=i
    
def del_Dataframes():
    del periods
    del custsup
    del vatcode
    del genledg
    del basics
    del openingsubBalance
    del openingBalance
    del subledger
    
# main program
inds_list = [] #blacklist

def get_table_download_link(df):
    """Generates a link allowing the data in a given panda dataframe to be downloaded
    in:  dataframe
    out: href string
    """
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()  # some strings <-> bytes conversions necessary here
    href = f'<a href="data:file/csv;base64,{b64}" download="transactions.csv">Download transactions.csv file</a>'
    return href

if __name__ == "__main__":
    direc = r"C:\Users\marte\OneDrive\Business\Taxsample\all_auditfiles\old"
    file='ExactOnline_V32_2016.xaf'
    result = st.empty()
    st.image(taxsample, format='PGN', width=100)
    st.title('Taxsample Upload Center')
    st.subheader('Upload your auditfile(.XAF). It will be converted to a Taxsample Output File')
    
    chart_data = pd.DataFrame(np.random.randn(20, 3),columns=['Tony Blair', 'Gerhard Schroeder', 'George Bush'])
    #st.area_chart(chart_data)
    


    add_selectbox = st.sidebar.selectbox('How would you like to be contacted?',('Email', 'Home phone', 'Mobile phone'))
    uploaded_xaf = st.file_uploader(label='upload your Auditfile here:', encoding='utf-8', type='xaf')
    #uploaded_xaf = io.TextIOWrapper(uploaded)
    if uploaded_xaf:

        result.info("Please wait for about 20 - 30 min for your file to be analysed ...")
        result.success("Conversion is done ! ")
        
        tree = ET.parse(uploaded_xaf) 
        root = tree.getroot()
        af_info,namespaces,ns,ns_raw,company, header, transactions=lees_metadata(root,uploaded_xaf)
        periods, custsup,vatcode,genledg,basics, openingsubBalance, openingBalance, subledger=lees_stamtabellen(namespaces, ns, company)
        journal_df,journals=lees_journal(namespaces, ns, company)
        tr=lees_trans(ns, journals)
        table_list=[tr, af_info, journal_df, periods, custsup,vatcode,genledg,basics, openingsubBalance, openingBalance, subledger]
        table_name=['tr', 'af_info', 'journal_df', 'periods', 'custsup','vatcode','genledg','basics', 'openingsubbalance', 'openingbalance', 'subledger']
        
        st.write( af_info.iloc[0])
        href=get_table_download_link(tr)
        #st.subheader(href)
        st.markdown(href, unsafe_allow_html=True)
        
    
    
    
    
    
    
