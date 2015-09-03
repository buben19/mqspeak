# Copyright (C) Ivo Slanina <ivo.slanina@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from mqspeak.data import DataIdentifier
import os
import paho.mqtt.client as mqtt
import socket
import sys
import threading

class BrokerThreadManager:
    """
    Manage broker receiving threads
    """

    def __init__(self, listenDescriptors, dataCollector):
        """
        listenDescriptors: listen descriptor iterable object
            broker: broker descriptor object
            subsriptionIterable:
        dataCollector: DataCollector object
        """
        self.idManager = BrokerReceiverIDManager()
        self.clients = [BrokerReceiver(self.idManager.createReceiverID(), x, dataCollector) for x in listenDescriptors]
        self.isThreadsRunning = False

    def start(self):
        """
        Start all receiving threads.
        """
        if self.isThreadsRunning:
            raise ThreadManagerException("Broker threads are already running")
        self.isThreadsRunning = True
        for client in self.clients:
            threading.Thread(target = client).start()

    def stop(self):
        """
        Stop all receving threads.
        """
        if not self.isThreadsRunning:
            raise ThreadManagerException("Broker threads are already stopped")
        self.isThreadsRunning = False
        for client in self.clients:
            client.stop()

class BrokerReceiver:
    """
    Broker receiving thread
    """

    def __init__(self, clientID, listenDescriptor, dataCollector):
        """
        listenDescriptor: set containing following fields: (broker, subscription)
            broker: broker descriptor object
            subscription:
        dataCollector: listener object to deliver received updates
        """
        (self.broker, self.subsciption) = listenDescriptor
        self.dataCollector = dataCollector
        self.clientID = clientID
        self.client = mqtt.Client(client_id = str(self.clientID))
        self._registerCallbacks()
        if self.broker.isAuthenticationRequired():
            self.client.username_pw_set(self.broker.user, self.broker.password)

    def _registerCallbacks(self):
        self.client.on_connect = self.onConnect
        self.client.on_disconnect = self.onDisconnect
        self.client.on_message = self.onMessage
        self.client.on_subscribe = self.onSubscribe
        self.client.on_unsubscribe = self.onUnsubscribe
        self.client.on_log = self.onLog

    def __call__(self):
        keepAliveInterval = 60
        self.client.connect(self.broker.host, self.broker.port, keepAliveInterval)
        self.client.loop_forever()

    def onConnect(self, client, userdata, flags, rc):
        """
        The callback for when the client receives a CONNACK response from the server.
        """
        print("Client {0} ({1} [{2}:{3}]): [{4}] {5}.".format(self.clientID, self.broker.name, self.broker.host, self.broker.port, rc, self._getClientConnectionStatus(rc)))
        for sub in self.subsciption:
            (result, mid) = self.client.subscribe(sub)

    def _getClientConnectionStatus(self, rc):
        if rc == 0:
            return "Connection successful"
        elif rc == 1:
            return "Connection refused - incorrect protocol version"
        elif rc == 2:
            return "Connection refused - invalid client identifier"
        elif rc == 3:
            return "Connection refused - server unavailable"
        elif rc == 4:
            return "Connection refused - bad username or password"
        elif rc == 5:
            return "Connection refused - not authorised"
        else:
            return "Unknown return code: {0}".format(rc)

    def onDisconnect(self, client, userdata, rc):
        """
        Callback when client is disconnected.
        """
        print("Client dicsconnect: {0}".format(rc))

    def onMessage(self, client, userdata, msg):
        """
        The callback for when a PUBLISH message is received from the server.
        """
        dataID = DataIdentifier(self.broker, msg.topic)
        try:
            data = msg.payload.decode("utf-8")
            self.dataCollector.onNewData(dataID, data)
        except UnicodeError as ex:
            print("Can't decode received message payload: {0}".format(msg.payload), file = sys.stderr)

    def onSubscribe(self, client, userdata, mid, granted_qos):
        """
        Callback when client is subscribed to topic.
        """

    def onUnsubscribe(self, client, userdata, mid):
        """
        Callback when client is unsubscribed.
        """

    def onLog(self, client, userdata, level, buf):
        """
        Logging messages.
        """

    def stop(self):
        """
        Stop receiver thread. Call this method to nicely end __call__() method.
        """
        self.client.disconnect()

class BrokerReceiverID:
    """
    Broker receiver thread ID.
    """

    def __init__(self, hostname, pid, receiverID):
        """
        Create broker receiver thread lient ID.

        hostname: machine hostname
        pid: current pid
        receiverID: receivin thread ID
        """
        self.hostname = hostname
        self.pid = pid
        self.receiverID = receiverID

    def __str__(self):
        return "mqspeak-{0}-{1}-{2}".format(self.hostname, self.pid, self.receiverID)

    def __repr__(self):
        return "<{0}>".format(self.__str__())

class BrokerReceiverIDManager:
    """
    Manage receiver IDs.
    """

    def __init__(self):
        self.hostname = socket.gethostname()
        self.pid = os.getpid()
        self.receiverCounter = 0

    def createReceiverID(self):
        _receiverID = self.receiverCounter
        self.receiverCounter += 1
        return BrokerReceiverID(self.hostname, self.pid, _receiverID)

class ThreadManagerException(Exception):
    """
    Indicate BrokerThreadManager error
    """
